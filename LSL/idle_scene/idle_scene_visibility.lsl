// Idle scene visibility controller for station-wide state changes.
integer SCENE_CHANNEL = -451210;
string STATE_VERSION = "IDLE_V22";

integer MSG_EDIT = 9101;
integer MSG_CALIBRATE = 9102;
integer MSG_SHOW = 9103;
integer MSG_PLAY = 9104;
integer MSG_RESET = 9105;
integer MSG_HIDE = 9106;

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
    if (value == "PAUSED") return "PAUSED";
    if (value == "PLAY") return "PLAY";
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
    string description = llGetObjectDesc();
    list fields = llParseStringKeepNulls(description, ["|"], []);
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
        "IDLE NO HOME / CALIBRATE FIRST: "
        + command
        + " diabaikan. Scene dan seluruh prim tetap pada posisi sekarang."
    );
}

enterRecovery()
{
    cancelPending();
    homeValid = FALSE;
    writePreHomeState("RECOVERY");
    llOwnerSay(
        "IDLE RECOVERY V2.2: scene tetap visible dan paused. Posisi tidak diubah. "
        + "HOME lama tanpa penanda IDLE_V22 diabaikan. NO HOME / CALIBRATE FIRST."
    );
}

enterEdit()
{
    cancelPending();

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
        llOwnerSay("IDLE EDIT: scene kembali ke HOME, visible, dan paused.");
    }
    else
    {
        llOwnerSay(
            "IDLE EDIT RECOVERY: mode EDIT disimpan sebagai STATE|IDLE_V22|EDIT. "
            + "HOME belum ada dan tidak ada prim yang dipindahkan."
        );
    }
}

calibrateHome()
{
    cancelPending();

    if (homeValid && currentMode == "HIDDEN")
    {
        llOwnerSay("IDLE CALIBRATE DITOLAK: scene sedang HIDDEN. Jalankan EDIT terlebih dahulu.");
        return;
    }

    if (homeValid && currentMode == "PLAY")
    {
        llOwnerSay("IDLE CALIBRATE DITOLAK: animasi sedang PLAY. Jalankan EDIT atau RESET terlebih dahulu.");
        return;
    }

    homePosition = llGetPos();
    homeRotation = llGetRot();
    homeValid = TRUE;
    writeHome("EDIT");
    llMessageLinked(LINK_SET, MSG_CALIBRATE, "CALIBRATE", NULL_KEY);
    llOwnerSay(
        "IDLE CALIBRATED: root serta posisi lokal dan rotasi lokal setiap anggota actor "
        + "disimpan. Mode persisten sekarang EDIT."
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

    moveHome();
    writeHome("PLAY");
    llMessageLinked(LINK_SET, MSG_SHOW, "SHOW", NULL_KEY);
    llMessageLinked(LINK_SET, MSG_PLAY, "AUTO_PLAY", NULL_KEY);
    llOwnerSay("IDLE SHOW: scene visible dan langsung bermain.");
}

playScene(string payload)
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("PLAY");
        return;
    }

    moveHome();
    writeHome("PLAY");
    llMessageLinked(LINK_SET, MSG_PLAY, payload, NULL_KEY);
    llOwnerSay("IDLE PLAY.");
}

resetScene()
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("RESET");
        return;
    }

    moveHome();
    writeHome("PAUSED");
    llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    llOwnerSay("IDLE RESET: seluruh actor kembali ke pose awal dan scene paused.");
}

hideScene()
{
    cancelPending();

    if (!homeValid)
    {
        denyNoHome("HIDE");
        return;
    }

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
                    "IDLE EDIT RECOVERY RESTORED: STATE|IDLE_V22|EDIT terbaca setelah Reset Scripts. "
                    + "HOME belum ada; scene dan seluruh prim tidak dipindahkan."
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
            llOwnerSay("IDLE AUTO-CALIBRATE ROOT: Reset Scripts dilakukan saat mode EDIT.");
            return;
        }

        if (currentMode == "HIDDEN")
        {
            moveHidden();
            llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
            llOwnerSay("IDLE HIDDEN: HOME lama dipertahankan. Posisi hidden tidak disimpan sebagai HOME.");
            return;
        }

        moveHome();
        if (currentMode == "PLAY")
        {
            writeHome("PLAY");
            llMessageLinked(LINK_SET, MSG_SHOW, "SHOW", NULL_KEY);
            llMessageLinked(LINK_SET, MSG_PLAY, "AUTO_RESUME", NULL_KEY);
            llOwnerSay("IDLE READY: animasi otomatis dilanjutkan.");
        }
        else
        {
            writeHome("PAUSED");
            llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
            llOwnerSay("IDLE READY: scene kembali ke HOME dan paused.");
        }
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
        else if (upper == "PLAY")
        {
            playScene("PLAY");
        }
        else if (llSubStringIndex(upper, "RESULT|") == 0)
        {
            playScene(trimmed);
        }
        else if (upper == "RESET")
        {
            resetScene();
        }
        else if (upper == "HIDE")
        {
            hideScene();
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
            llOwnerSay("IDLE HIDE GAGAL: root tidak dapat dipindahkan. Scene dikembalikan ke HOME.");
            return;
        }

        llMessageLinked(LINK_SET, MSG_HIDE, "HIDE", NULL_KEY);
        llOwnerSay("IDLE HIDE: actor sudah di-reset, lalu root dipindahkan tanpa mengubah alpha.");
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
