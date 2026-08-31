// River scene controller: coordinate river actors and backend animation events.
integer MASTER_CHANNEL = -451200;
integer SCENE_CHANNEL = -451233;
string STATE_VERSION = "RIVER_V1";

integer MSG_EDIT = 9701;
integer MSG_CALIBRATE = 9702;
integer MSG_SHOW = 9703;
integer MSG_RESET = 9704;
integer MSG_HIDE = 9705;
integer MSG_ACTION = 9710;
integer MSG_ACTION_DONE = 9711;

integer MAX_STEPS = 40;
integer MAX_RESULT_CHARS = 1200;
vector HIDE_OFFSET = <0.0, 0.0, 1000.0>;

vector homePosition;
rotation homeRotation;
integer homeValid = FALSE;
string currentMode = "RECOVERY";
integer listenHandle;

list sequenceSteps = [];
integer stepIndex = 0;
integer sequenceRunning = FALSE;
integer waitingActor = FALSE;
string activeRunId = "";
string lastResult = "";

string trim(string value) { return llStringTrim(value, STRING_TRIM); }
string upper(string value) { return llToUpper(trim(value)); }
integer ownerCommand(key id) { return llGetOwnerKey(id) == llGetOwner(); }

integer readState()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    if (llGetListLength(fields) >= 5 && upper(llList2String(fields, 0)) == "HOME" && upper(llList2String(fields, 1)) == STATE_VERSION)
    {
        homePosition = (vector)llList2String(fields, 2);
        homeRotation = (rotation)llList2String(fields, 3);
        currentMode = upper(llList2String(fields, 4));
        homeValid = TRUE;
        return TRUE;
    }
    homeValid = FALSE;
    currentMode = "RECOVERY";
    if (llGetListLength(fields) >= 3 && upper(llList2String(fields, 0)) == "STATE" && upper(llList2String(fields, 1)) == STATE_VERSION)
    {
        currentMode = upper(llList2String(fields, 2));
    }
    return FALSE;
}

writePreHome(string modeValue)
{
    currentMode = upper(modeValue);
    if (currentMode != "EDIT") currentMode = "RECOVERY";
    llSetObjectDesc("STATE|" + STATE_VERSION + "|" + currentMode);
}

writeHome(string modeValue)
{
    currentMode = upper(modeValue);
    llSetObjectDesc("HOME|" + STATE_VERSION + "|" + (string)homePosition + "|" + (string)homeRotation + "|" + currentMode);
}

moveHome()
{
    if (!homeValid) return;
    llSetRegionPos(homePosition);
    llSetRot(homeRotation);
}

moveHidden()
{
    if (!homeValid) return;
    llSetRegionPos(homePosition + HIDE_OFFSET);
    llSetRot(homeRotation);
}

denyNoHome(string command)
{
    llOwnerSay("RIVER NO HOME / CALIBRATE FIRST: " + command + " diabaikan.");
}

stopSequence()
{
    sequenceSteps = [];
    stepIndex = 0;
    sequenceRunning = FALSE;
    waitingActor = FALSE;
    llSetTimerEvent(0.0);
}

string stepKey(string step)
{
    list kv = llParseStringKeepNulls(step, ["="], []);
    return upper(llList2String(kv, 0));
}

string stepValue(string step)
{
    list kv = llParseStringKeepNulls(step, ["="], []);
    if (llGetListLength(kv) < 2) return "";
    return trim(llDumpList2String(llList2List(kv, 1, -1), "="));
}

integer validActor(string value)
{
    value = upper(value);
    return value == "GEMBALA" || value == "SERIGALA" || value == "DOMBA" || value == "RUMPUT";
}

integer validActorList(string value)
{
    list actors = llParseString2List(upper(value), ["+"], []);
    integer count = llGetListLength(actors);
    if (!count || count > 2) return FALSE;
    integer i;
    for (i = 0; i < count; i++) if (!validActor(llList2String(actors, i))) return FALSE;
    return TRUE;
}

integer validateSequence(list steps)
{
    integer count = llGetListLength(steps);
    if (!count || count > MAX_STEPS) return FALSE;
    integer i;
    for (i = 0; i < count; i++)
    {
        string step = trim(llList2String(steps, i));
        string keyValue = stepKey(step);
        string value = stepValue(step);
        if (keyValue == "LOAD" || keyValue == "UNLOAD")
        {
            if (!validActorList(value)) return FALSE;
        }
        else if (keyValue == "BOAT")
        {
            value = upper(value);
            if (!(value == "LEFT" || value == "RIGHT")) return FALSE;
        }
        else if (keyValue == "WAIT")
        {
            float seconds = (float)value;
            if (seconds < 0.0 || seconds > 10.0) return FALSE;
        }
        else if (keyValue == "INVALID" || keyValue == "SUCCESS")
        {
        }
        else return FALSE;
    }
    return TRUE;
}

runNext()
{
    if (!sequenceRunning || waitingActor) return;
    if (stepIndex >= llGetListLength(sequenceSteps))
    {
        sequenceRunning = FALSE;
        writeHome("PAUSED");
        llRegionSay(MASTER_CHANNEL, "ANIMATION_DONE|" + activeRunId);
        llOwnerSay("RIVER RESULT SELESAI: " + (string)stepIndex + " step.");
        return;
    }

    string step = trim(llList2String(sequenceSteps, stepIndex));
    stepIndex++;
    if (stepKey(step) == "WAIT")
    {
        float seconds = (float)stepValue(step);
        if (seconds < 0.05) seconds = 0.05;
        llSetTimerEvent(seconds);
        return;
    }

    waitingActor = TRUE;
    llMessageLinked(LINK_SET, MSG_ACTION, step, NULL_KEY);
}

startResult(string message)
{
    if (!homeValid) { denyNoHome("RESULT"); return; }
    if (llStringLength(message) > MAX_RESULT_CHARS)
    {
        llOwnerSay("RIVER RESULT DITOLAK: payload terlalu panjang.");
        return;
    }
    list parts = llParseStringKeepNulls(message, ["|"], []);
    if (llGetListLength(parts) < 4 || upper(llList2String(parts, 1)) != "RIVER")
    {
        llOwnerSay("RIVER RESULT DITOLAK: format harus RESULT|RIVER|RUN_ID|STEPS.");
        return;
    }
    list steps = llParseStringKeepNulls(llList2String(parts, 3), [">"], []);
    if (!validateSequence(steps))
    {
        llOwnerSay("RIVER RESULT DITOLAK: step atau parameter tidak valid.");
        return;
    }

    stopSequence();
    moveHome();
    llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    writeHome("PLAY");
    activeRunId = trim(llList2String(parts, 2));
    sequenceSteps = steps;
    sequenceRunning = TRUE;
    lastResult = message;
    runNext();
}

handleCommand(string message)
{
    string command = upper(message);
    if (command == "EDIT")
    {
        stopSequence();
        if (homeValid) { moveHome(); writeHome("EDIT"); }
        else writePreHome("EDIT");
        llMessageLinked(LINK_SET, MSG_EDIT, "EDIT", NULL_KEY);
        llOwnerSay("RIVER EDIT: visible dan paused.");
    }
    else if (command == "CALIBRATE")
    {
        stopSequence();
        if (homeValid && (currentMode == "PLAY" || currentMode == "HIDDEN"))
        {
            llOwnerSay("RIVER CALIBRATE DITOLAK: jalankan EDIT dahulu.");
            return;
        }
        homePosition = llGetPos();
        homeRotation = llGetRot();
        homeValid = TRUE;
        writeHome("EDIT");
        llMessageLinked(LINK_SET, MSG_CALIBRATE, "CALIBRATE", NULL_KEY);
        llOwnerSay("RIVER CALIBRATED: boat dan seluruh actor disimpan.");
    }
    else if (command == "SHOW")
    {
        if (!homeValid) { denyNoHome("SHOW"); return; }
        stopSequence(); moveHome(); writeHome("PAUSED");
        llMessageLinked(LINK_SET, MSG_SHOW, "SHOW", NULL_KEY);
    }
    else if (command == "RESET")
    {
        if (!homeValid) { denyNoHome("RESET"); return; }
        stopSequence(); moveHome(); writeHome("PAUSED");
        llMessageLinked(LINK_SET, MSG_RESET, "RESET", NULL_KEY);
    }
    else if (command == "HIDE")
    {
        if (!homeValid) { denyNoHome("HIDE"); return; }
        stopSequence(); llMessageLinked(LINK_SET, MSG_HIDE, "HIDE", NULL_KEY);
        moveHidden(); writeHome("HIDDEN");
    }
    else if (command == "PLAY")
    {
        if (lastResult == "") llOwnerSay("RIVER PLAY DITOLAK: belum ada RESULT terakhir.");
        else startResult(lastResult);
    }
    else if (llSubStringIndex(command, "RESULT|RIVER|") == 0) startResult(message);
}

default
{
    state_entry()
    {
        listenHandle = llListen(SCENE_CHANNEL, "", NULL_KEY, "");
        readState();
        stopSequence();
        if (!homeValid)
        {
            writePreHome(currentMode);
            llOwnerSay("RIVER RECOVERY V1: visible dan paused; posisi tidak diubah. NO HOME / CALIBRATE FIRST.");
        }
        else if (currentMode == "HIDDEN") moveHidden();
        else if (currentMode == "EDIT")
        {
            homePosition = llGetPos();
            homeRotation = llGetRot();
            writeHome("EDIT");
        }
        else
        {
            moveHome();
            writeHome("PAUSED");
        }
    }

    listen(integer channel, string name, key id, string message)
    {
        if (ownerCommand(id)) handleCommand(message);
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_ACTION_DONE)
        {
            waitingActor = FALSE;
            runNext();
        }
    }

    timer()
    {
        llSetTimerEvent(0.0);
        runNext();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
    }
}
