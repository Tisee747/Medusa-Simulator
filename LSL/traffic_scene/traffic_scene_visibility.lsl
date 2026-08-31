// Traffic visibility controller: show or hide traffic scene components.
integer SCENE_CHANNEL = -451230;
string STATE_VERSION = "TRAFFIC_V1";

integer MSG_EDIT = 9201;
integer MSG_CALIBRATE = 9202;
integer MSG_SHOW = 9203;
integer MSG_RESULT = 9204;
integer MSG_RESET = 9205;
integer MSG_HIDE = 9206;
integer MSG_CANCEL = 9207;
integer MSG_RESULT_SEQ = 9208;
integer MSG_STEP_LIGHT = 9209;

integer MAX_SEQUENCE_STEPS = 10;

vector HIDE_OFFSET = <0.0, 0.0, 1000.0>;
float HIDE_DELAY = 0.25;

vector homePosition;
rotation homeRotation;
integer homeValid = FALSE;
string currentMode = "RECOVERY";
integer listenHandle = 0;
integer pendingHide = FALSE;

string cleanHomeMode(string value)
{
    value = llToUpper(llStringTrim(value, STRING_TRIM));

    if (value == "EDIT") return "EDIT";
    if (value == "PLAY") return "PLAY";
    if (value == "PAUSED") return "PAUSED";
    if (value == "HIDDEN") return "HIDDEN";

    return "PAUSED";
}

string cleanPreHomeMode(string value)
{
    value = llToUpper(llStringTrim(value, STRING_TRIM));

    if (value == "EDIT") return "EDIT";
    return "RECOVERY";
}

integer readPersistentState()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    integer count = llGetListLength(fields);

    if (
        count >= 5
        && llToUpper(llList2String(fields, 0)) == "HOME"
        && llToUpper(llList2String(fields, 1)) == STATE_VERSION
    )
    {
        homePosition = (vector)llList2String(fields, 2);
        homeRotation = (rotation)llList2String(fields, 3);
        currentMode = cleanHomeMode(llList2String(fields, 4));
        homeValid = TRUE;
        return TRUE;
    }

    homeValid = FALSE;

    if (
        count >= 3
        && llToUpper(llList2String(fields, 0)) == "STATE"
        && llToUpper(llList2String(fields, 1)) == STATE_VERSION
    )
    {
        currentMode = cleanPreHomeMode(llList2String(fields, 2));
    }
    else
    {
        currentMode = "RECOVERY";
    }

    return FALSE;
}

writeHome(string mode)
{
    currentMode = cleanHomeMode(mode);
    llSetObjectDesc(
        "HOME|"
        + STATE_VERSION
        + "|"
        + (string)homePosition
        + "|"
        + (string)homeRotation
        + "|"
        + currentMode
    );
}

writePreHomeState(string mode)
{
    currentMode = cleanPreHomeMode(mode);
    llSetObjectDesc("STATE|" + STATE_VERSION + "|" + currentMode);
}

cancelPending()
{
    pendingHide = FALSE;
    llSetTimerEvent(0.0);
}

cancelActors(string reason)
{
    llMessageLinked(LINK_SET, MSG_CANCEL, reason, NULL_KEY);
}

integer moveRoot(vector targetPosition, rotation targetRotation)
{
    integer moved = llSetRegionPos(targetPosition);
    llSetRot(targetRotation);
    return moved;
}

integer moveHome()
{
    if (!homeValid) return FALSE;
    return moveRoot(homePosition, homeRotation);
}

integer moveHidden()
{
    if (!homeValid) return FALSE;
    return moveRoot(homePosition + HIDE_OFFSET, homeRotation);
}

integer isOwnerCommand(key id)
{
    return llGetOwnerKey(id) == llGetOwner();
}

denyNoHome(string command)
{
    llOwnerSay(
        "TRAFFIC NO HOME / CALIBRATE FIRST: "
        + command
        + " diabaikan. Scene dan seluruh prim tetap pada posisi sekarang."
    );
}

integer validateResultSequence(string payload)
{
    list parts = llParseStringKeepNulls(payload, ["|"], []);

    if (llGetListLength(parts) != 4)
    {
        llOwnerSay(
            "TRAFFIC RESULT_SEQ DITOLAK: format harus "
            + "RESULT_SEQ|attempt_id|jumlah_step|step_data."
        );
        return FALSE;
    }

    string attempt = llStringTrim(llList2String(parts, 1), STRING_TRIM);
    integer declaredCount = (integer)llStringTrim(llList2String(parts, 2), STRING_TRIM);

    if (attempt == "")
    {
        llOwnerSay("TRAFFIC RESULT_SEQ DITOLAK: attempt_id kosong.");
        return FALSE;
    }

    if (declaredCount < 1 || declaredCount > MAX_SEQUENCE_STEPS)
    {
        llOwnerSay(
            "TRAFFIC RESULT_SEQ DITOLAK: jumlah_step harus 1 sampai "
            + (string)MAX_SEQUENCE_STEPS + "."
        );
        return FALSE;
    }

    list steps = llParseStringKeepNulls(llList2String(parts, 3), [";"], []);
    integer actualCount = llGetListLength(steps);

    if (actualCount != declaredCount)
    {
        llOwnerSay(
            "TRAFFIC RESULT_SEQ DITOLAK: jumlah_step="
            + (string)declaredCount
            + " tetapi step yang diterima="
            + (string)actualCount + "."
        );
        return FALSE;
    }

    integer i;

    for (i = 0; i < actualCount; i++)
    {
        list stepFields = llParseStringKeepNulls(
            llList2String(steps, i),
            ["~"],
            []
        );

        if (llGetListLength(stepFields) != 3)
        {
            llOwnerSay(
                "TRAFFIC RESULT_SEQ DITOLAK: step "
                + (string)(i + 1)
                + " harus berformat warna~actual~expected."
            );
            return FALSE;
        }
    }

    return TRUE;
}

enterRecovery()
{
    cancelPending();
    cancelActors("RECOVERY");
    homeValid = FALSE;
    writePreHomeState("RECOVERY");
    llOwnerSay(
        "TRAFFIC RECOVERY V1: scene tetap visible dan paused. Posisi tidak diubah. "
        + "HOME lama tanpa penanda TRAFFIC_V1 diabaikan. NO HOME / CALIBRATE FIRST."
    );
}

enterEdit()
{
    cancelPending();
    cancelActors("EDIT");

    if (homeValid)
    {
        moveHome();
        writeHome("EDIT");
    }
    else
    {
        writePreHomeState("EDIT");
    }

    llMessageLinked(LINK_SET, MSG_EDIT, "EDIT", NULL_KEY);

    if (homeValid)
    {
        llOwnerSay("TRAFFIC EDIT: sequence dibatalkan, scene kembali ke HOME, visible, dan paused.");
    }
    else
    {
        llOwnerSay(
            "TRAFFIC EDIT RECOVERY: mode EDIT disimpan persisten. "
            + "HOME belum ada dan tidak ada prim yang dipindahkan."
        );
    }
}

calibrateHome()
{
    cancelPending();

    if (homeValid && currentMode == "HIDDEN")
    {
        llOwnerSay("TRAFFIC CALIBRATE DITOLAK: scene sedang HIDDEN. Jalankan EDIT terlebih dahulu.");
        return;
    }

    if (homeValid && currentMode == "PLAY")
    {
        llOwnerSay("TRAFFIC CALIBRATE DITOLAK: animasi sedang PLAY. Jalankan EDIT terlebih dahulu.");
        return;
    }

    // Jangan kirim MSG_CANCEL sebelum kalibrasi. Pada source lama,
    // MSG_CANCEL dengan alasan CALIBRATE mengembalikan mobil ke HOME lama,
    // lalu MSG_CALIBRATE menyimpan posisi lama itu lagi.
    homePosition = llGetPos();
    homeRotation = llGetRot();
    homeValid = TRUE;
    writeHome("EDIT");

    // Actor menerima MSG_CALIBRATE dan menangkap posisi lokal mobil saat ini.
    // captureHome() di actor juga menghentikan timer/run aktif tanpa reset posisi.
    llMessageLinked(LINK_SET, MSG_CALIBRATE, "CALIBRATE", NULL_KEY);

    llOwnerSay(
        "TRAFFIC CALIBRATED CURRENT POSITION: root dan actor saat ini disimpan sebagai HOME baru. "
        + "Mode persisten sekarang EDIT."
    );
}

showScene()
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("SHOW");
        return;
    }

    cancelActors("SHOW");
    moveHome();
    writeHome("PAUSED");
    llMessageLinked(LINK_SET, MSG_SHOW, "SHOW", NULL_KEY);
    llOwnerSay("TRAFFIC SHOW: animasi dibatalkan, scene visible di HOME dan paused.");
}

playResult(string payload)
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("RESULT");
        return;
    }

    list parts = llParseStringKeepNulls(payload, ["|"], []);

    if (llGetListLength(parts) < 7)
    {
        llOwnerSay("TRAFFIC RESULT DITOLAK: format RESULT tidak lengkap.");
        return;
    }

    cancelActors("RESULT BARU");
    moveHome();
    writeHome("PLAY");
    llMessageLinked(LINK_SET, MSG_RESULT, payload, NULL_KEY);

    llOwnerSay(
        "TRAFFIC PREVIEW: lampu="
        + llList2String(parts, 4)
        + " | actual="
        + llList2String(parts, 5)
        + " | expected="
        + llList2String(parts, 6)
    );
}

playResultSequence(string payload)
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("RESULT_SEQ");
        return;
    }

    if (!validateResultSequence(payload))
    {
        llOwnerSay("TRAFFIC RESULT_SEQ: command baru ditolak; animasi yang sedang berjalan tidak ditumpuk.");
        return;
    }

    list parts = llParseStringKeepNulls(payload, ["|"], []);
    string attempt = llStringTrim(llList2String(parts, 1), STRING_TRIM);
    integer stepCount = (integer)llStringTrim(llList2String(parts, 2), STRING_TRIM);

    cancelActors("RESULT_SEQ BARU");
    moveHome();
    writeHome("PLAY");
    llMessageLinked(LINK_SET, MSG_RESULT_SEQ, payload, NULL_KEY);

    llOwnerSay(
        "TRAFFIC RESULT_SEQ START: attempt="
        + attempt
        + " | jumlah_step="
        + (string)stepCount
        + " | sequence lama sudah dibatalkan."
    );
}

resetScene()
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("RESET");
        return;
    }

    cancelActors("RESET");
    moveHome();
    writeHome("PAUSED");
    llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    llOwnerSay("TRAFFIC RESET: sequence dibatalkan; kendaraan dan lampu kembali ke pose awal.");
}

hideScene()
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("HIDE");
        return;
    }

    cancelActors("HIDE");
    moveHome();
    writeHome("HIDDEN");
    llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    pendingHide = TRUE;
    llSetTimerEvent(HIDE_DELAY);
}

default
{
    state_entry()
    {
        if (listenHandle)
        {
            llListenRemove(listenHandle);
        }

        listenHandle = llListen(SCENE_CHANNEL, "", NULL_KEY, "");
        cancelPending();

        if (!readPersistentState())
        {
            if (currentMode == "EDIT")
            {
                writePreHomeState("EDIT");
                llOwnerSay(
                    "TRAFFIC EDIT RECOVERY RESTORED: HOME belum ada; "
                    + "scene dan seluruh prim tidak dipindahkan."
                );
            }
            else
            {
                enterRecovery();
            }
            return;
        }

        if (currentMode == "EDIT")
        {
            homePosition = llGetPos();
            homeRotation = llGetRot();
            writeHome("EDIT");
            llOwnerSay("TRAFFIC AUTO-CALIBRATE ROOT: Reset Scripts dilakukan saat mode EDIT.");
            return;
        }

        if (currentMode == "HIDDEN")
        {
            moveHidden();
            llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
            llOwnerSay("TRAFFIC HIDDEN: HOME lama dipertahankan. Posisi hidden tidak disimpan sebagai HOME.");
            return;
        }

        moveHome();
        writeHome("PAUSED");
        llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
        llOwnerSay("TRAFFIC READY: pose tengah tidak disimpan. Scene kembali ke HOME dan paused.");
    }

    listen(integer channel, string name, key id, string message)
    {
        if (channel != SCENE_CHANNEL || !isOwnerCommand(id)) return;

        string trimmed = llStringTrim(message, STRING_TRIM);
        string upper = llToUpper(trimmed);

        if (upper == "EDIT")
        {
            enterEdit();
        }
        else if (upper == "CALIBRATE")
        {
            calibrateHome();
        }
        else if (upper == "SHOW")
        {
            showScene();
        }
        else if (llSubStringIndex(upper, "RESULT_SEQ|") == 0)
        {
            playResultSequence(trimmed);
        }
        else if (llSubStringIndex(upper, "RESULT|") == 0)
        {
            playResult(trimmed);
        }
        else if (upper == "RESET")
        {
            resetScene();
        }
        else if (upper == "HIDE")
        {
            hideScene();
        }
        else if (upper == "PLAY")
        {
            llOwnerSay(
                "TRAFFIC PLAY: gunakan RESULT|... untuk satu kasus atau "
                + "RESULT_SEQ|attempt_id|jumlah_step|warna~actual~expected;... untuk sequence."
            );
        }
    }

    timer()
    {
        if (!pendingHide)
        {
            llSetTimerEvent(0.0);
            return;
        }

        pendingHide = FALSE;
        llSetTimerEvent(0.0);

        if (currentMode != "HIDDEN") return;

        if (!moveHidden())
        {
            moveHome();
            writeHome("PAUSED");
            llOwnerSay("TRAFFIC HIDE GAGAL: root tidak dapat dipindahkan. Scene dikembalikan ke HOME.");
            return;
        }

        llMessageLinked(LINK_SET, MSG_HIDE, "HIDE", NULL_KEY);
        llOwnerSay("TRAFFIC HIDE: sequence dibatalkan, actor di-reset, lalu root dipindahkan tanpa alpha.");
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
