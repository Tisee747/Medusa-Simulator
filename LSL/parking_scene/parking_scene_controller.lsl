// Parking scene controller: coordinate vehicle, barrier, and display actors.
integer MASTER_CHANNEL = -451200;
integer SCENE_CHANNEL = -451231;

integer MSG_EDIT = 9401;
integer MSG_CALIBRATE = 9402;
integer MSG_SHOW = 9403;
integer MSG_RESET = 9404;
integer MSG_HIDE = 9405;

integer MSG_VEHICLE_ACTION = 9410;
integer MSG_VEHICLE_DONE = 9411;
integer MSG_BARRIER_ACTION = 9420;
integer MSG_BARRIER_DONE = 9421;
integer MSG_DISPLAY_SET = 9430;
integer MSG_GATE_STATE = 9431;

string STATE_VERSION = "PARKING_V21";
float HIDE_HEIGHT = 1000.0;
integer MAX_STEPS = 40;
integer MAX_SEQUENCE_CHARS = 900;
float STEP_GAP = 0.08;
float DEFAULT_STOP_WAIT = 0.55;

integer WAIT_NONE = 0;
integer WAIT_ADVANCE = 1;
integer WAIT_VEHICLE = 2;
integer WAIT_BARRIER = 3;
integer WAIT_TIME = 4;
integer WAIT_STOP = 5;
integer WAIT_START = 6;

integer homeValid = FALSE;
vector homePosition = ZERO_VECTOR;
rotation homeRotation = ZERO_ROTATION;
string mode = "RECOVERY";

list sequenceSteps = [];
integer stepIndex = 0;
integer sequenceRunning = FALSE;
integer waitKind = WAIT_NONE;
string activeVehicle = "";
string runId = "";
string lastSequence = "";
string lastRunId = "";
integer barrierOpen = FALSE;
string validationError = "";
string validationVehicle = "";

string trim(string value)
{
    return llStringTrim(value, STRING_TRIM);
}

string upper(string value)
{
    return llToUpper(trim(value));
}

integer startsWith(string value, string prefix)
{
    return llSubStringIndex(value, prefix) == 0;
}

integer isOwnerSpeaker(key speaker)
{
    return llGetOwnerKey(speaker) == llGetOwner();
}

integer isVehicle(string value)
{
    value = upper(value);
    return value == "MOTOR" || value == "MOBIL" || value == "TRUK";
}

integer isNumber(string value)
{
    value = trim(value);
    integer length = llStringLength(value);
    if (length == 0) return FALSE;

    integer dots = 0;
    integer digits = 0;
    integer i;

    for (i = 0; i < length; i++)
    {
        string character = llGetSubString(value, i, i);

        if (character == ".")
        {
            dots++;
            if (dots > 1) return FALSE;
        }
        else if (llSubStringIndex("0123456789", character) != -1)
        {
            digits++;
        }
        else
        {
            return FALSE;
        }
    }

    return digits > 0;
}

string decodedText(string value)
{
    return llDumpList2String(llParseStringKeepNulls(value, ["_"], []), " ");
}

integer readPersistentState()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    integer count = llGetListLength(fields);

    homeValid = FALSE;
    mode = "RECOVERY";

    if (
        count >= 5
        && upper(llList2String(fields, 0)) == "HOME"
        && upper(llList2String(fields, 1)) == STATE_VERSION
    )
    {
        homePosition = (vector)llList2String(fields, 2);
        homeRotation = (rotation)llList2String(fields, 3);
        mode = upper(llList2String(fields, 4));
        homeValid = TRUE;
        return TRUE;
    }

    if (
        count >= 3
        && upper(llList2String(fields, 0)) == "STATE"
        && upper(llList2String(fields, 1)) == STATE_VERSION
    )
    {
        mode = upper(llList2String(fields, 2));
        if (mode != "EDIT") mode = "RECOVERY";
    }

    return FALSE;
}

writeRecovery(string nextMode)
{
    mode = upper(nextMode);
    llSetObjectDesc("STATE|" + STATE_VERSION + "|" + mode);
}

writeHome(string nextMode)
{
    mode = upper(nextMode);
    llSetObjectDesc(
        "HOME|" + STATE_VERSION
        + "|" + (string)homePosition
        + "|" + (string)homeRotation
        + "|" + mode
    );
}

vector hiddenPosition()
{
    return homePosition + <0.0, 0.0, HIDE_HEIGHT>;
}

moveRoot(vector position, rotation rot)
{
    llSetRot(rot);
    llSetRegionPos(position);
}

sendDisplay(string value)
{
    llMessageLinked(LINK_SET, MSG_DISPLAY_SET, value, NULL_KEY);
}

sendGate(string value)
{
    llMessageLinked(LINK_SET, MSG_GATE_STATE, upper(value), NULL_KEY);
}

stopRuntime()
{
    sequenceRunning = FALSE;
    sequenceSteps = [];
    stepIndex = 0;
    waitKind = WAIT_NONE;
    activeVehicle = "";
    runId = "";
    barrierOpen = FALSE;
    llSetTimerEvent(0.0);
}

rejectNoHome(string command)
{
    llOwnerSay("PARKING NO HOME / CALIBRATE FIRST: " + command + " diabaikan.");
}

scheduleAdvance(float delay)
{
    waitKind = WAIT_ADVANCE;
    if (delay < 0.05) delay = 0.05;
    llSetTimerEvent(delay);
}

resetActors()
{
    barrierOpen = FALSE;
    llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    sendGate("CLOSED");
    sendDisplay("");
}

restorePaused()
{
    stopRuntime();
    moveRoot(homePosition, homeRotation);
    resetActors();
    writeHome("PAUSED");
}

enterEdit()
{
    stopRuntime();

    if (!homeValid)
    {
        writeRecovery("EDIT");
        llMessageLinked(LINK_SET, MSG_EDIT, "EDIT_RECOVERY", NULL_KEY);
        llOwnerSay("PARKING EDIT RECOVERY: visible dan paused; tidak ada prim yang dipindahkan.");
        return;
    }

    moveRoot(homePosition, homeRotation);
    writeHome("EDIT");
    llMessageLinked(LINK_SET, MSG_EDIT, "EDIT", NULL_KEY);
    sendGate("CLOSED");
    sendDisplay("EDIT MODE");
    llOwnerSay("PARKING EDIT: seluruh kendaraan dikembalikan ke HOME untuk pemeriksaan.");
}

calibrate()
{
    if (!homeValid && mode != "EDIT" && mode != "RECOVERY")
    {
        llOwnerSay("PARKING CALIBRATE DITOLAK: masuk EDIT terlebih dahulu.");
        return;
    }

    if (homeValid && mode != "EDIT")
    {
        llOwnerSay("PARKING CALIBRATE DITOLAK: tekan EDIT dan hentikan animasi dahulu.");
        return;
    }

    stopRuntime();
    homePosition = llGetPos();
    homeRotation = llGetRot();
    homeValid = TRUE;
    writeHome("EDIT");
    llMessageLinked(LINK_SET, MSG_CALIBRATE, "CALIBRATE", NULL_KEY);
    sendGate("CLOSED");
    sendDisplay("CALIBRATED");
    llOwnerSay("PARKING CALIBRATED: root dan HOME seluruh actor disimpan sebagai PARKING_V21.");
}

showScene()
{
    if (!homeValid)
    {
        rejectNoHome("SHOW");
        return;
    }

    restorePaused();
    sendDisplay("PARKING READY");
    llOwnerSay("PARKING SHOW: visible dan paused.");
}

resetScene()
{
    if (!homeValid)
    {
        rejectNoHome("RESET");
        return;
    }

    restorePaused();
    llOwnerSay("PARKING RESET: sequence berhenti, barrier tertutup, kendaraan di-reset.");
}

hideScene()
{
    if (!homeValid)
    {
        rejectNoHome("HIDE");
        return;
    }

    stopRuntime();
    moveRoot(homePosition, homeRotation);
    resetActors();
    writeHome("HIDDEN");
    llSetRegionPos(hiddenPosition());
    llOwnerSay("PARKING HIDE: scene dipindahkan tanpa alpha.");
}

string stepValue(string step, string wantedKey)
{
    list pairs = llParseStringKeepNulls(step, [","], []);
    integer count = llGetListLength(pairs);
    integer i;

    wantedKey = upper(wantedKey);

    for (i = 0; i < count; i++)
    {
        string pair = trim(llList2String(pairs, i));
        integer equalIndex = llSubStringIndex(pair, "=");

        if (equalIndex > 0)
        {
            string keyName = upper(llGetSubString(pair, 0, equalIndex - 1));
            if (keyName == wantedKey)
            {
                return trim(llGetSubString(pair, equalIndex + 1, -1));
            }
        }
    }

    return "";
}

string stepCommand(string step)
{
    list parts = llParseStringKeepNulls(step, [","], []);
    string first = upper(llList2String(parts, 0));
    if (llSubStringIndex(first, "=") == -1) return first;

    string action = upper(stepValue(step, "ACTION"));
    if (action != "") return action;
    if (stepValue(step, "BARRIER") != "") return "BARRIER";
    if (stepValue(step, "DISPLAY") != "") return "DISPLAY";
    if (stepValue(step, "WAIT") != "") return "WAIT";
    return "";
}

string firstValue(string step, string preferredKey, string legacyKey)
{
    string value = stepValue(step, preferredKey);
    if (value == "" && legacyKey != "") value = stepValue(step, legacyKey);
    return value;
}

integer validatePairKeys(string step)
{
    list pairs = llParseStringKeepNulls(step, [","], []);
    integer count = llGetListLength(pairs);
    integer i;

    for (i = 0; i < count; i++)
    {
        string pair = trim(llList2String(pairs, i));
        integer equalIndex = llSubStringIndex(pair, "=");

        if (i == 0 && equalIndex == -1)
        {
            string command = upper(pair);
            if (
                command != "SHOW" && command != "APPROACH" && command != "STOP"
                && command != "ENTER" && command != "EXIT" && command != "HIDE"
                && command != "RESET" && command != "BARRIER"
                && command != "DISPLAY" && command != "WAIT"
            )
            {
                validationError = "command tidak dikenal: " + command;
                return FALSE;
            }
        }
        else
        {
            if (equalIndex <= 0)
            {
                validationError = "pasangan KEY=VALUE tidak valid: " + pair;
                return FALSE;
            }

            string keyName = upper(llGetSubString(pair, 0, equalIndex - 1));
            string value = trim(llGetSubString(pair, equalIndex + 1, -1));

            if (value == "")
            {
                validationError = "nilai kosong untuk " + keyName;
                return FALSE;
            }

            if (
                keyName != "ACTOR" && keyName != "VEHICLE" && keyName != "ACTION"
                && keyName != "AT" && keyName != "DIRECTION"
                && keyName != "STATE" && keyName != "BARRIER"
                && keyName != "TEXT" && keyName != "DISPLAY"
                && keyName != "SECONDS" && keyName != "WAIT"
            )
            {
                validationError = "key tidak dikenal: " + keyName;
                return FALSE;
            }
        }
    }

    return TRUE;
}

integer validateStep(string step, integer number)
{
    step = trim(step);

    if (step == "")
    {
        validationError = "step " + (string)number + " kosong";
        return FALSE;
    }

    if (!validatePairKeys(step))
    {
        validationError = "step " + (string)number + ": " + validationError;
        return FALSE;
    }

    string command = stepCommand(step);
    string vehicle = upper(firstValue(step, "ACTOR", "VEHICLE"));
    string action = upper(stepValue(step, "ACTION"));
    string atValue = upper(stepValue(step, "AT"));
    string direction = upper(stepValue(step, "DIRECTION"));
    string barrier = upper(firstValue(step, "STATE", "BARRIER"));
    string displayValue = firstValue(step, "TEXT", "DISPLAY");
    string waitValue = firstValue(step, "SECONDS", "WAIT");

    if (action == "" && (command == "SHOW" || command == "APPROACH" || command == "STOP"
        || command == "ENTER" || command == "EXIT" || command == "HIDE" || command == "RESET"))
        action = command;
    if (command == "BARRIER" && barrier == "") barrier = upper(stepValue(step, "BARRIER"));

    if (vehicle != "")
    {
        if (!isVehicle(vehicle))
        {
            validationError = "step " + (string)number + ": VEHICLE harus MOTOR, MOBIL, atau TRUK";
            return FALSE;
        }
        validationVehicle = vehicle;
    }

    integer primaryCount = 0;
    if (action != "") primaryCount++;
    if (barrier != "") primaryCount++;
    if (displayValue != "") primaryCount++;
    if (waitValue != "") primaryCount++;

    if (primaryCount > 1)
    {
        validationError = "step " + (string)number + ": hanya satu ACTION/BARRIER/DISPLAY/WAIT per step";
        return FALSE;
    }

    if (primaryCount == 0 && vehicle == "")
    {
        validationError = "step " + (string)number + ": tidak ada perintah";
        return FALSE;
    }

    if (action != "")
    {
        if (
            action != "SHOW"
            && action != "APPROACH"
            && action != "STOP"
            && action != "ENTER"
            && action != "EXIT"
            && action != "HIDE"
            && action != "RESET"
        )
        {
            validationError = "step " + (string)number + ": ACTION tidak valid: " + action;
            return FALSE;
        }

        if (validationVehicle == "")
        {
            validationError = "step " + (string)number + ": pilih VEHICLE sebelum ACTION";
            return FALSE;
        }

        if (atValue != "" && action != "SHOW")
        {
            validationError = "step " + (string)number + ": AT hanya untuk ACTION=SHOW";
            return FALSE;
        }

        if (atValue != "" && atValue != "START" && atValue != "END")
        {
            validationError = "step " + (string)number + ": AT harus START atau END";
            return FALSE;
        }

        if (direction != "" && action != "APPROACH")
        {
            validationError = "step " + (string)number + ": DIRECTION hanya untuk ACTION=APPROACH";
            return FALSE;
        }

        if (direction != "" && direction != "ENTER" && direction != "EXIT")
        {
            validationError = "step " + (string)number + ": DIRECTION harus ENTER atau EXIT";
            return FALSE;
        }
    }
    else if (atValue != "" || direction != "")
    {
        validationError = "step " + (string)number + ": AT/DIRECTION membutuhkan ACTION";
        return FALSE;
    }

    if (barrier != "" && barrier != "OPEN" && barrier != "CLOSE")
    {
        validationError = "step " + (string)number + ": BARRIER harus OPEN atau CLOSE";
        return FALSE;
    }

    if (displayValue != "" && llStringLength(displayValue) > 80)
    {
        validationError = "step " + (string)number + ": DISPLAY maksimal 80 karakter";
        return FALSE;
    }

    if (waitValue != "")
    {
        if (!isNumber(waitValue))
        {
            validationError = "step " + (string)number + ": WAIT harus angka";
            return FALSE;
        }

        float seconds = (float)waitValue;
        if (seconds < 0.05 || seconds > 10.0)
        {
            validationError = "step " + (string)number + ": WAIT harus 0.05 sampai 10 detik";
            return FALSE;
        }
    }

    return TRUE;
}

integer validateSequence(string sequence)
{
    sequenceSteps = llParseStringKeepNulls(sequence, [">"], []);
    integer count = llGetListLength(sequenceSteps);

    validationError = "";
    validationVehicle = "";

    if (count < 1)
    {
        validationError = "sequence kosong";
        return FALSE;
    }

    if (llStringLength(sequence) > MAX_SEQUENCE_CHARS)
    {
        validationError = "sequence maksimal " + (string)MAX_SEQUENCE_CHARS + " karakter";
        return FALSE;
    }

    if (count > MAX_STEPS)
    {
        validationError = "maksimal " + (string)MAX_STEPS + " step";
        return FALSE;
    }

    integer i;
    for (i = 0; i < count; i++)
    {
        if (!validateStep(llList2String(sequenceSteps, i), i + 1)) return FALSE;
    }

    return TRUE;
}

finishSequence()
{
    sequenceRunning = FALSE;
    waitKind = WAIT_NONE;
    llSetTimerEvent(0.0);
    writeHome("PAUSED");

    string completion = "ANIMATION_DONE|PARKING";
    if (runId != "") completion += "|" + runId;
    llRegionSay(MASTER_CHANNEL, completion);

    sendDisplay("SEQUENCE DONE");
    llOwnerSay("PARKING RESULT SELESAI: " + (string)llGetListLength(sequenceSteps) + " step.");
}

executeNextStep()
{
    if (!sequenceRunning) return;

    if (stepIndex >= llGetListLength(sequenceSteps))
    {
        finishSequence();
        return;
    }

    string step = trim(llList2String(sequenceSteps, stepIndex));
    stepIndex++;

    string command = stepCommand(step);
    string vehicle = upper(firstValue(step, "ACTOR", "VEHICLE"));
    string action = upper(stepValue(step, "ACTION"));
    string atValue = upper(stepValue(step, "AT"));
    string direction = upper(stepValue(step, "DIRECTION"));
    string barrier = upper(firstValue(step, "STATE", "BARRIER"));
    string displayValue = firstValue(step, "TEXT", "DISPLAY");
    string waitValue = firstValue(step, "SECONDS", "WAIT");

    if (action == "" && (command == "SHOW" || command == "APPROACH" || command == "STOP"
        || command == "ENTER" || command == "EXIT" || command == "HIDE" || command == "RESET"))
        action = command;
    if (command == "BARRIER" && barrier == "") barrier = upper(stepValue(step, "BARRIER"));

    if (vehicle != "") activeVehicle = vehicle;

    if (action == "")
    {
        if (barrier != "")
        {
            waitKind = WAIT_BARRIER;
            if (barrier == "OPEN") sendGate("OPENING");
            else sendGate("CLOSING");
            llMessageLinked(LINK_SET, MSG_BARRIER_ACTION, barrier, NULL_KEY);
            return;
        }

        if (displayValue != "")
        {
            sendDisplay(decodedText(displayValue));
            scheduleAdvance(STEP_GAP);
            return;
        }

        if (waitValue != "")
        {
            waitKind = WAIT_TIME;
            llSetTimerEvent((float)waitValue);
            return;
        }

        scheduleAdvance(STEP_GAP);
        return;
    }

    if (action == "STOP")
    {
        sendDisplay(activeVehicle + " STOP");
        waitKind = WAIT_STOP;
        llSetTimerEvent(DEFAULT_STOP_WAIT);
        return;
    }

    if ((action == "ENTER" || action == "EXIT") && !barrierOpen)
    {
        sendDisplay(activeVehicle + " BLOCKED\nBARRIER CLOSED");
        waitKind = WAIT_STOP;
        llSetTimerEvent(0.80);
        return;
    }

    string parameter = "";
    if (action == "SHOW")
    {
        // Default PARKING adalah kendaraan keluar: mulai dari sisi dalam/kanan.
        if (atValue == "") atValue = "END";
        parameter = atValue;
    }
    else if (action == "APPROACH")
    {
        // Default PARKING adalah EXIT menuju gerbang pembayaran.
        if (direction == "") direction = "EXIT";
        parameter = direction;
    }

    waitKind = WAIT_VEHICLE;
    llMessageLinked(
        LINK_SET,
        MSG_VEHICLE_ACTION,
        action + "|" + activeVehicle + "|" + parameter,
        NULL_KEY
    );
}

startSequence(string suppliedRunId, string sequence)
{
    if (!homeValid)
    {
        rejectNoHome("PLAY / RESULT");
        return;
    }

    if (!validateSequence(sequence))
    {
        llOwnerSay("PARKING RESULT DITOLAK: " + validationError + ". Tidak ada actor yang dipindahkan.");
        sequenceSteps = [];
        return;
    }

    stopRuntime();
    sequenceSteps = llParseStringKeepNulls(sequence, [">"], []);
    stepIndex = 0;
    sequenceRunning = TRUE;
    activeVehicle = "";
    runId = suppliedRunId;
    barrierOpen = FALSE;
    lastSequence = sequence;
    lastRunId = suppliedRunId;

    moveRoot(homePosition, homeRotation);
    resetActors();
    writeHome("PLAY");
    sendDisplay("PARKING RUN");
    waitKind = WAIT_START;
    llSetTimerEvent(0.15);
}

handleResult(string message)
{
    list fields = llParseStringKeepNulls(message, ["|"], []);
    integer count = llGetListLength(fields);

    if (count < 3 || upper(llList2String(fields, 0)) != "RESULT" || upper(llList2String(fields, 1)) != "PARKING")
    {
        llOwnerSay("PARKING RESULT DITOLAK: format harus RESULT|PARKING|<sequence>.");
        return;
    }

    string suppliedRunId = "";
    string sequence = "";

    if (count >= 4)
    {
        suppliedRunId = trim(llList2String(fields, 2));
        sequence = trim(llList2String(fields, 3));
    }
    else
    {
        sequence = trim(llList2String(fields, 2));
    }

    startSequence(suppliedRunId, sequence);
}

handleCommand(string message)
{
    string command = upper(message);

    if (command == "EDIT") enterEdit();
    else if (command == "CALIBRATE") calibrate();
    else if (command == "SHOW") showScene();
    else if (command == "RESET") resetScene();
    else if (command == "HIDE") hideScene();
    else if (command == "PLAY")
    {
        if (lastSequence == "")
        {
            llOwnerSay("PARKING PLAY DITOLAK: belum ada RESULT valid pada runtime ini.");
        }
        else
        {
            startSequence(lastRunId, lastSequence);
        }
    }
    else if (startsWith(command, "RESULT|PARKING|"))
    {
        handleResult(message);
    }
    else
    {
        llOwnerSay("PARKING COMMAND TIDAK DIKENAL: " + message);
    }
}

default
{
    state_entry()
    {
        llListen(SCENE_CHANNEL, "", NULL_KEY, "");
        stopRuntime();
        readPersistentState();

        if (!homeValid)
        {
            if (mode == "EDIT") writeRecovery("EDIT");
            else writeRecovery("RECOVERY");

            llOwnerSay("PARKING RECOVERY V2.1: visible dan paused; posisi tidak diubah. NO HOME / CALIBRATE FIRST.");
        }
        else if (mode == "EDIT")
        {
            homePosition = llGetPos();
            homeRotation = llGetRot();
            writeHome("EDIT");
            llOwnerSay("PARKING EDIT RESTORED: Reset Scripts saat EDIT memperbarui HOME root visible.");
        }
        else if (mode == "HIDDEN")
        {
            writeHome("HIDDEN");
            llSetRegionPos(hiddenPosition());
            llOwnerSay("PARKING HIDDEN RESTORED: HOME lama dipertahankan.");
        }
        else
        {
            moveRoot(homePosition, homeRotation);
            resetActors();
            writeHome("PAUSED");
            llOwnerSay("PARKING READY: pose tengah tidak disimpan; scene kembali HOME dan paused.");
        }
    }

    listen(integer channel, string name, key speaker, string message)
    {
        if (channel != SCENE_CHANNEL) return;
        if (!isOwnerSpeaker(speaker)) return;
        handleCommand(message);
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (!sequenceRunning) return;

        if (number == MSG_VEHICLE_DONE && waitKind == WAIT_VEHICLE)
        {
            waitKind = WAIT_NONE;
            scheduleAdvance(STEP_GAP);
        }
        else if (number == MSG_BARRIER_DONE && waitKind == WAIT_BARRIER)
        {
            string result = upper(message);
            if (result == "OPEN") barrierOpen = TRUE;
            else barrierOpen = FALSE;
            if (barrierOpen) sendGate("OPEN");
            else sendGate("CLOSED");
            waitKind = WAIT_NONE;
            scheduleAdvance(STEP_GAP);
        }
    }

    timer()
    {
        llSetTimerEvent(0.0);

        if (!sequenceRunning) return;

        if (
            waitKind == WAIT_ADVANCE
            || waitKind == WAIT_TIME
            || waitKind == WAIT_STOP
            || waitKind == WAIT_START
        )
        {
            waitKind = WAIT_NONE;
            executeNextStep();
        }
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
