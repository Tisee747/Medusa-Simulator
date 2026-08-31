// Rescue scene controller: coordinate the rescue actor and backend payloads.
integer MASTER_CHANNEL = -451200;
integer SCENE_CHANNEL = -451234;
integer VISIBILITY_CHANNEL = -451299;
integer ACTOR_CHANNEL = -451235;
integer LINK_CONTROLLER_TO_ACTOR = 451235;
integer LINK_ACTOR_TO_CONTROLLER = 451236;

integer TRANSPORT_NONE = 0;
integer TRANSPORT_LINK = 1;
integer TRANSPORT_REGION = 2;

string SCENE_CODE = "RESCUE";
string SCENE_CODE_LEGACY = "RESCUE_RL";

integer MAX_STEPS = 60;
integer MAX_PAYLOAD_CHARS = 1600;
integer ACTOR_READY_TIMEOUT_SECONDS = 8;
integer ACTION_TIMEOUT_SECONDS = 20;

vector sceneHomePosition;
rotation sceneHomeRotation;
vector sceneHiddenPosition;
integer sceneVisible = FALSE;

list runSteps = [];
integer runIndex = 0;
integer runActive = FALSE;
integer waitingForActorReady = FALSE;
integer waitingForActorAction = FALSE;
integer deadlineUnix = 0;
string activeRunId = "";
string expectedAction = "";
string pingToken = "";
key actorObjectKey = NULL_KEY;
integer actorReady = FALSE;
integer actorTransport = 0;
integer actorRobotCount = 0;
integer actorBeaconCount = 0;
integer statusRequested = FALSE;

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

integer sceneAliasMatches(string value)
{
    value = upper(value);
    if (value == SCENE_CODE) return TRUE;
    if (value == SCENE_CODE_LEGACY) return TRUE;
    return FALSE;
}

integer coordinateValid(string value)
{
    list parts = llParseStringKeepNulls(value, [","], []);
    if (llGetListLength(parts) != 2) return FALSE;

    string rowText = trim(llList2String(parts, 0));
    string columnText = trim(llList2String(parts, 1));
    if (rowText == "" || columnText == "") return FALSE;

    integer row = (integer)rowText;
    integer column = (integer)columnText;
    if ((string)row != rowText || (string)column != columnText) return FALSE;
    if (row < 0 || row > 4 || column < 0 || column > 4) return FALSE;
    return TRUE;
}

integer directionValid(string value)
{
    value = upper(value);
    if (value == "UP") return TRUE;
    if (value == "DOWN") return TRUE;
    if (value == "LEFT") return TRUE;
    if (value == "RIGHT") return TRUE;
    return FALSE;
}

string actionKey(string step)
{
    list parts = llParseStringKeepNulls(step, ["="], []);
    return upper(llList2String(parts, 0));
}

integer terminalAction(string keyValue)
{
    if (keyValue == "GOAL") return TRUE;
    if (keyValue == "HIT_WALL") return TRUE;
    if (keyValue == "OUT_OF_GRID") return TRUE;
    if (keyValue == "INVALID_STEP") return TRUE;
    if (keyValue == "INCOMPLETE") return TRUE;
    return FALSE;
}

integer actionValid(string step, integer index, integer count)
{
    if (step == "") return FALSE;
    if (llSubStringIndex(step, "|") >= 0) return FALSE;
    if (llSubStringIndex(step, ">") >= 0) return FALSE;

    list fields = llParseStringKeepNulls(step, ["="], []);
    string keyValue = upper(llList2String(fields, 0));
    string value = "";
    if (llGetListLength(fields) > 1)
        value = trim(llDumpList2String(llList2List(fields, 1, -1), "="));

    if (keyValue == "START")
    {
        if (index != 0) return FALSE;
        return coordinateValid(value);
    }
    if (index == 0) return FALSE;

    if (keyValue == "MOVE") return directionValid(value);

    if (keyValue == "GOAL" || keyValue == "HIT_WALL")
    {
        if (index != count - 1) return FALSE;
        return coordinateValid(value);
    }

    if (keyValue == "OUT_OF_GRID")
    {
        if (index != count - 1) return FALSE;
        return directionValid(value);
    }

    if (keyValue == "INVALID_STEP")
    {
        if (index != count - 1) return FALSE;
        return value != "";
    }

    if (keyValue == "INCOMPLETE")
    {
        if (index != count - 1) return FALSE;
        return llGetListLength(fields) == 1;
    }

    return FALSE;
}

integer validateSequence(string sequence)
{
    if (sequence == "") return FALSE;
    list steps = llParseStringKeepNulls(sequence, [">"], []);
    integer count = llGetListLength(steps);
    if (count < 2 || count > MAX_STEPS) return FALSE;

    integer terminalSeen = FALSE;
    integer i;
    for (i = 0; i < count; i++)
    {
        string step = trim(llList2String(steps, i));
        string keyValue = actionKey(step);
        if (terminalSeen) return FALSE;
        if (!actionValid(step, i, count)) return FALSE;
        if (terminalAction(keyValue)) terminalSeen = TRUE;
    }

    if (!terminalSeen) return FALSE;
    runSteps = steps;
    return TRUE;
}

setSceneVisible(integer show)
{
    if (show)
    {
        llSetRegionPos(sceneHomePosition);
        llSetRot(sceneHomeRotation);
        llSetStatus(STATUS_PHANTOM, FALSE);
        sceneVisible = TRUE;
    }
    else
    {
        llSetStatus(STATUS_PHANTOM, TRUE);
        llSetRegionPos(sceneHiddenPosition);
        sceneVisible = FALSE;
    }
}

sendActorMessage(string message)
{
    if (actorTransport == TRANSPORT_LINK)
    {
        llMessageLinked(LINK_SET, LINK_CONTROLLER_TO_ACTOR, message, llGetKey());
        return;
    }

    if (actorTransport == TRANSPORT_REGION && actorObjectKey != NULL_KEY)
    {
        llRegionSayTo(actorObjectKey, ACTOR_CHANNEL, message);
        return;
    }

    // Discovery mode: linked message works when both scripts are in one object.
    // Region message works when actor is placed in a separate object.
    llMessageLinked(LINK_SET, LINK_CONTROLLER_TO_ACTOR, message, llGetKey());
    llRegionSay(ACTOR_CHANNEL, message);
}

sendActorControl(string command)
{
    string token = (string)llGetUnixTime() + "-" + (string)((integer)llFrand(999999.0));
    sendActorMessage("CTL|" + token + "|" + upper(command));
}

requestActorReady()
{
    actorReady = FALSE;
    actorTransport = TRANSPORT_NONE;
    actorObjectKey = NULL_KEY;
    actorRobotCount = 0;
    actorBeaconCount = 0;
    pingToken = (string)llGetUnixTime() + "-" + (string)((integer)llFrand(999999.0));

    // Wajib memakai dual transport. Jika controller dan actor berada
    // dalam linkset yang sama, PING diterima melalui link_message.
    // Regional channel tetap menjadi fallback untuk object terpisah.
    sendActorMessage("PING|" + pingToken);
}

clearRun()
{
    runSteps = [];
    runIndex = 0;
    runActive = FALSE;
    waitingForActorReady = FALSE;
    waitingForActorAction = FALSE;
    deadlineUnix = 0;
    activeRunId = "";
    expectedAction = "";
    llSetTimerEvent(0.0);
}

cancelRun(string actorCommand)
{
    clearRun();
    if (actorCommand != "") sendActorControl(actorCommand);
}

failRun(string detail)
{
    string failedId = activeRunId;
    clearRun();
    llOwnerSay("RESCUE V8 ERROR: " + detail + " | run=" + failedId + ". ACK sukses tidak dikirim.");
}

finishRun()
{
    string completedId = activeRunId;
    clearRun();
    llRegionSay(MASTER_CHANNEL, "ANIMATION_DONE|RESCUE|" + completedId);
    llOwnerSay("RESCUE V8 SELESAI: run=" + completedId + ".");
}

sendNextAction()
{
    if (!runActive) return;
    if (waitingForActorReady) return;
    if (waitingForActorAction) return;

    if (runIndex >= llGetListLength(runSteps))
    {
        finishRun();
        return;
    }

    string step = trim(llList2String(runSteps, runIndex));
    expectedAction = actionKey(step);
    waitingForActorAction = TRUE;
    deadlineUnix = llGetUnixTime() + ACTION_TIMEOUT_SECONDS;
    llSetTimerEvent(1.0);
    sendActorMessage(
        "ACT|" + activeRunId
        + "|" + (string)runIndex
        + "|" + step
    );
}

startRun(string runId, string sequence)
{
    cancelRun("RESET");

    activeRunId = trim(runId);
    if (activeRunId == "")
    {
        failRun("animation_run_id kosong");
        return;
    }

    if (!validateSequence(sequence))
    {
        failRun("sequence ditolak oleh validator");
        return;
    }

    runIndex = 0;
    runActive = TRUE;
    waitingForActorReady = TRUE;
    waitingForActorAction = FALSE;
    deadlineUnix = llGetUnixTime() + ACTOR_READY_TIMEOUT_SECONDS;
    llSetTimerEvent(1.0);
    requestActorReady();
}

handleResult(string message)
{
    if (llStringLength(message) > MAX_PAYLOAD_CHARS)
    {
        llOwnerSay("RESCUE V8 RESULT DITOLAK: payload melebihi 1600 karakter.");
        return;
    }

    list fields = llParseStringKeepNulls(message, ["|"], []);
    if (llGetListLength(fields) != 4)
    {
        llOwnerSay("RESCUE V8 RESULT DITOLAK: harus tepat empat field.");
        return;
    }

    if (upper(llList2String(fields, 0)) != "RESULT")
    {
        llOwnerSay("RESCUE V8 RESULT DITOLAK: prefix RESULT tidak ditemukan.");
        return;
    }

    if (!sceneAliasMatches(llList2String(fields, 1)))
    {
        llOwnerSay("RESCUE V8 RESULT DITOLAK: scene harus RESCUE.");
        return;
    }

    startRun(llList2String(fields, 2), llList2String(fields, 3));
}

handleActorMessage(key speaker, string message, integer transport)
{
    if (!isOwnerSpeaker(speaker)) return;

    list fields = llParseStringKeepNulls(message, ["|"], []);
    string command = upper(llList2String(fields, 0));

    if (command == "READY")
    {
        if (llGetListLength(fields) < 6) return;
        if (llList2String(fields, 1) != pingToken) return;
        if (upper(llList2String(fields, 2)) != "OK")
        {
            llOwnerSay("RESCUE V8: actor ditemukan tetapi belum siap: " + message);
            return;
        }

        integer robotCount = (integer)llList2String(fields, 3);
        integer beaconCount = (integer)llList2String(fields, 4);
        integer homeReady = (integer)llList2String(fields, 5);
        if (robotCount < 1 || beaconCount < 1 || !homeReady)
        {
            llOwnerSay("RESCUE V8: actor tidak lengkap. robot=" + (string)robotCount + ", beacon=" + (string)beaconCount + ", home=" + (string)homeReady + ".");
            return;
        }

        actorObjectKey = speaker;
        actorTransport = transport;
        actorRobotCount = robotCount;
        actorBeaconCount = beaconCount;
        actorReady = TRUE;
        llOwnerSay(
            "RESCUE V8 ACTOR READY: transport=" + (string)actorTransport
            + ", object=" + (string)actorObjectKey
            + ", robot=" + (string)actorRobotCount
            + ", beacon=" + (string)actorBeaconCount + "."
        );

        if (statusRequested)
        {
            statusRequested = FALSE;
            llOwnerSay(
                "RESCUE V8 STATUS: visible=" + (string)sceneVisible
                + ", actorReady=1"
                + ", transport=" + (string)actorTransport
                + ", robotParts=" + (string)actorRobotCount
                + ", beaconParts=" + (string)actorBeaconCount
                + ", runActive=" + (string)runActive
                + "."
            );
            if (!runActive)
            {
                deadlineUnix = 0;
                llSetTimerEvent(0.0);
            }
        }

        if (runActive && waitingForActorReady)
        {
            waitingForActorReady = FALSE;
            deadlineUnix = 0;
            sendNextAction();
        }
        return;
    }

    if (command == "DONE")
    {
        if (speaker != actorObjectKey) return;
        if (!runActive || !waitingForActorAction) return;
        if (llGetListLength(fields) < 5) return;

        string doneRunId = trim(llList2String(fields, 1));
        integer doneIndex = (integer)llList2String(fields, 2);
        string resultType = upper(llList2String(fields, 3));
        string detail = upper(llList2String(fields, 4));

        if (doneRunId != activeRunId) return;
        if (doneIndex != runIndex) return;

        waitingForActorAction = FALSE;
        deadlineUnix = 0;

        if (resultType == "ERROR")
        {
            failRun("actor melaporkan " + llList2String(fields, 4));
            return;
        }

        if (resultType != "OK")
        {
            failRun("format jawaban actor tidak dikenal");
            return;
        }

        if (detail != expectedAction)
        {
            failRun("action selesai tidak sesuai urutan: " + detail + " != " + expectedAction);
            return;
        }

        runIndex++;
        sendNextAction();
        return;
    }
}

handleVisibilityBus(integer channel, key speaker, string message)
{
    if (channel != VISIBILITY_CHANNEL) return;
    if (!isOwnerSpeaker(speaker)) return;

    string command = upper(message);
    if (command == "HIDE_ALL")
    {
        cancelRun("HIDE");
        setSceneVisible(FALSE);
        return;
    }

    if (startsWith(command, "SHOW_ONLY|"))
    {
        string requestedScene = upper(llGetSubString(command, 10, -1));
        if (sceneAliasMatches(requestedScene))
        {
            cancelRun("SHOW");
            setSceneVisible(TRUE);
        }
        else
        {
            cancelRun("HIDE");
            setSceneVisible(FALSE);
        }
    }
}

default
{
    state_entry()
    {
        sceneHomePosition = llGetPos();
        sceneHomeRotation = llGetRot();
        sceneHiddenPosition = sceneHomePosition + <0.0, 0.0, 1000.0>;

        llListen(SCENE_CHANNEL, "", NULL_KEY, "");
        llListen(VISIBILITY_CHANNEL, "", NULL_KEY, "");
        llListen(ACTOR_CHANNEL, "", NULL_KEY, "");

        clearRun();
        sendActorControl("HIDE");
        setSceneVisible(FALSE);
        requestActorReady();
        llOwnerSay("RESCUE V8 READY: actor bridge linked+regional aktif; scene RESCUE dan RESCUE_RL diterima.");
    }

    listen(integer channel, string name, key speaker, string message)
    {
        if (channel == ACTOR_CHANNEL)
        {
            // Ignore chat emitted by this same object. Same-object actor uses link_message.
            if (speaker == llGetKey()) return;
            handleActorMessage(speaker, message, TRANSPORT_REGION);
            return;
        }

        if (channel == VISIBILITY_CHANNEL)
        {
            handleVisibilityBus(channel, speaker, message);
            return;
        }

        if (channel != SCENE_CHANNEL) return;
        if (!isOwnerSpeaker(speaker)) return;

        string command = upper(message);
        if (command == "SHOW")
        {
            cancelRun("SHOW");
            setSceneVisible(TRUE);
        }
        else if (command == "EDIT")
        {
            cancelRun("EDIT");
            setSceneVisible(TRUE);
        }
        else if (command == "CALIBRATE")
        {
            cancelRun("CALIBRATE");
            sceneHomePosition = llGetPos();
            sceneHomeRotation = llGetRot();
            sceneHiddenPosition = sceneHomePosition + <0.0, 0.0, 1000.0>;
            setSceneVisible(TRUE);
        }
        else if (command == "HIDE")
        {
            cancelRun("HIDE");
            setSceneVisible(FALSE);
        }
        else if (command == "RESET")
        {
            cancelRun("RESET");
        }
        else if (command == "STATUS")
        {
            statusRequested = TRUE;
            deadlineUnix = llGetUnixTime() + ACTOR_READY_TIMEOUT_SECONDS;
            llSetTimerEvent(1.0);
            requestActorReady();
            llOwnerSay("RESCUE V8 STATUS: memeriksa actor...");
        }
        else if (startsWith(command, "RESULT|"))
        {
            setSceneVisible(TRUE);
            handleResult(message);
        }
    }

    link_message(integer senderNumber, integer number, string message, key id)
    {
        if (number != LINK_ACTOR_TO_CONTROLLER) return;
        handleActorMessage(id, message, TRANSPORT_LINK);
    }

    timer()
    {
        if (deadlineUnix == 0) return;
        if (llGetUnixTime() <= deadlineUnix) return;

        if (statusRequested && !runActive)
        {
            statusRequested = FALSE;
            deadlineUnix = 0;
            llSetTimerEvent(0.0);
            llOwnerSay("RESCUE V8 STATUS ERROR: actor tidak menjawab PING. Pastikan Actor V4 aktif pada linkset Rescue yang sama.");
            return;
        }

        if (!runActive) return;

        if (waitingForActorReady)
            failRun("actor tidak menjawab PING. Pastikan actor V4 dipasang pada root/linkset Rescue yang memuat robot dan beacon");
        else if (waitingForActorAction)
            failRun("actor melewati batas waktu action " + expectedAction);
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
    }
}
