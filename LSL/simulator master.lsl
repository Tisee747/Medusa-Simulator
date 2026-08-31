// Master controller: route station commands and backend state to each scene.
integer MASTER_CHANNEL = -451200;
integer VISIBILITY_CHANNEL = -451299;

integer IDLE_CHANNEL = -451210;
integer TRAFFIC_CHANNEL = -451230;
integer PARKING_CHANNEL = -451231;
integer PACKAGE_CHANNEL = -451232;
integer RIVER_CHANNEL = -451233;
integer RESCUE_CHANNEL = -451234;

// Configure privately for the target deployment; keep infrastructure URLs out of source control.
string API_BASE = "";
string MASTER_VERSION = "MASTER_V15_HTTP_VISIBILITY";

float TIMER_STEP = 0.25;
float SWITCH_DELAY = 0.70;
float SAME_SCENE_DELAY = 0.10;
float POLL_INTERVAL = 2.00;
float RUN_TIMEOUT = 240.0;

integer masterListen = 0;
integer dialogListen = 0;
integer dialogChannel = 0;
key dialogUser = NULL_KEY;

integer initialized = FALSE;
string activeScene = "";
string persistentMode = "READY";

string pendingScene = "";
string pendingCommand = "";
integer pendingStartsRun = FALSE;
integer pendingFromBackend = FALSE;
string pendingRunId = "";
float pendingElapsed = 0.0;
float pendingDelay = 0.0;

integer busy = FALSE;
string busyScene = "";
string busyRunId = "";
integer busyFromBackend = FALSE;
float busyElapsed = 0.0;

float pollElapsed = 0.0;
integer lastStateVersion = -1;
string backendStatus = "UNKNOWN";
string backendScene = "";
string backendAttempt = "";
string currentPage = "";

key requestStart = NULL_KEY;
key requestState = NULL_KEY;
key requestPlay = NULL_KEY;
key requestReset = NULL_KEY;
key requestNew = NULL_KEY;
key requestFinish = NULL_KEY;
key requestHome = NULL_KEY;

list MAIN_BUTTONS = [
    "IDLE", "TRAFFIC", "PARKING",
    "PACKAGE", "RIVER", "RESCUE",
    "RESET", "HIDE ALL", "TOOLS", "STATUS"
];

list TOOL_BUTTONS = [
    "EDIT", "CALIBRATE", "SHOW",
    "PLAY", "HIDE", "ABORT",
    "INIT", "BACK"
];

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

string normalizeScene(string value)
{
    value = upper(value);

    if (value == "IDLE") return "IDLE";
    if (value == "TRAFFIC") return "TRAFFIC";
    if (value == "PARKING") return "PARKING";
    if (value == "PACKAGE" || value == "PACKAGE_SORT" || value == "PACKAGE SORT") return "PACKAGE";
    if (value == "RIVER") return "RIVER";
    if (value == "RESCUE" || value == "RESCUE_RL" || value == "RESCUE RL") return "RESCUE";

    return "";
}

string backendSceneName(string normalized)
{
    normalized = normalizeScene(normalized);
    if (normalized == "PACKAGE") return "PACKAGE_SORT";
    if (normalized == "RESCUE") return "RESCUE_RL";
    return normalized;
}

integer sceneChannel(string scene)
{
    scene = normalizeScene(scene);

    if (scene == "IDLE") return IDLE_CHANNEL;
    if (scene == "TRAFFIC") return TRAFFIC_CHANNEL;
    if (scene == "PARKING") return PARKING_CHANNEL;
    if (scene == "PACKAGE") return PACKAGE_CHANNEL;
    if (scene == "RIVER") return RIVER_CHANNEL;
    if (scene == "RESCUE") return RESCUE_CHANNEL;

    return 0;
}

sendScene(string scene, string message)
{
    integer channel = sceneChannel(scene);

    if (channel == 0)
    {
        llOwnerSay("MASTER ERROR: scene tidak dikenal: " + scene);
        return;
    }

    llRegionSay(channel, message);
}

sendMasterEvent(string message)
{
    llRegionSay(MASTER_CHANNEL, message);
}

syncVisibility(string scene)
{
    scene = normalizeScene(scene);

    if (scene == "")
    {
        llRegionSay(VISIBILITY_CHANNEL, "HIDE_ALL");
        return;
    }

    llRegionSay(
        VISIBILITY_CHANNEL,
        "SHOW_ONLY|" + backendSceneName(scene)
    );
}

writePersistent(string modeValue)
{
    persistentMode = upper(modeValue);
    if (persistentMode != "BUSY") persistentMode = "READY";

    string savedScene = activeScene;
    if (savedScene == "") savedScene = "NONE";

    llSetObjectDesc(
        "MASTER|" + MASTER_VERSION
        + "|" + savedScene
        + "|" + persistentMode
        + "|" + (string)initialized
    );
}

readPersistent()
{
    initialized = FALSE;
    activeScene = "";
    persistentMode = "READY";

    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    if (llGetListLength(fields) < 4) return;
    if (upper(llList2String(fields, 0)) != "MASTER") return;

    string version = upper(llList2String(fields, 1));
    if (version != MASTER_VERSION && version != "MASTER_V14_HTTP" && version != "MASTER_V13_HTTP" && version != "MASTER_V12_HTTP" && version != "MASTER_V11") return;

    activeScene = normalizeScene(llList2String(fields, 2));
    if (upper(llList2String(fields, 3)) == "BUSY") persistentMode = "BUSY";

    if (version == "MASTER_V11") initialized = TRUE;
    else if (llGetListLength(fields) >= 5) initialized = (integer)llList2String(fields, 4);
}

hideMasterVisual()
{
    llSetLinkAlpha(LINK_SET, 0.0, ALL_SIDES);
    llSetText("", ZERO_VECTOR, 0.0);
    llSetStatus(STATUS_PHANTOM, TRUE);
    llSetClickAction(CLICK_ACTION_TOUCH);
}

updateHover()
{
    llSetText("", ZERO_VECTOR, 0.0);
}

closeDialog()
{
    if (dialogListen)
    {
        llListenRemove(dialogListen);
        dialogListen = 0;
    }
    dialogUser = NULL_KEY;
}

openMainDialog(key user)
{
    closeDialog();
    dialogUser = user;
    dialogListen = llListen(dialogChannel, "", user, "");

    string sceneText = activeScene;
    if (sceneText == "") sceneText = "NONE";

    string stateText = "READY";
    if (!initialized) stateText = "PRESS INIT";
    else if (busy) stateText = "BUSY: " + busyScene;

    llDialog(
        user,
        "SIMULATOR MASTER\nActive: " + sceneText
        + "\nState: " + stateText
        + "\nBackend: " + backendStatus,
        MAIN_BUTTONS,
        dialogChannel
    );
}

openToolsDialog(key user)
{
    closeDialog();
    dialogUser = user;
    dialogListen = llListen(dialogChannel, "", user, "");

    string sceneText = activeScene;
    if (sceneText == "") sceneText = "NONE";

    llDialog(user, "MASTER TOOLS\nTarget: " + sceneText, TOOL_BUTTONS, dialogChannel);
}

hideOtherScenes(string keepScene)
{
    syncVisibility(keepScene);

    list scenes = ["IDLE", "TRAFFIC", "PARKING", "PACKAGE", "RIVER", "RESCUE"];
    integer i;
    for (i = 0; i < llGetListLength(scenes); i++)
    {
        string scene = llList2String(scenes, i);
        if (scene != keepScene) sendScene(scene, "HIDE");
    }
}

hideAllScenes()
{
    syncVisibility("");

    list scenes = ["IDLE", "TRAFFIC", "PARKING", "PACKAGE", "RIVER", "RESCUE"];
    integer i;
    for (i = 0; i < llGetListLength(scenes); i++) sendScene(llList2String(scenes, i), "HIDE");

    activeScene = "";
    pendingScene = "";
    pendingCommand = "";
    pendingStartsRun = FALSE;
    pendingFromBackend = FALSE;
    pendingRunId = "";
    busy = FALSE;
    busyScene = "";
    busyRunId = "";
    busyFromBackend = FALSE;
    busyElapsed = 0.0;
    writePersistent("READY");
    updateHover();

    llOwnerSay("MASTER: seluruh scene disembunyikan.");
}

string resultScene(string message)
{
    list fields = llParseStringKeepNulls(message, ["|"], []);
    integer count = llGetListLength(fields);
    if (count < 2 || upper(llList2String(fields, 0)) != "RESULT") return "";

    string scene = normalizeScene(llList2String(fields, 1));
    if (scene != "") return scene;

    if (count >= 3) return normalizeScene(llList2String(fields, 2));
    return "";
}

string resultRunId(string message, string scene)
{
    list fields = llParseStringKeepNulls(message, ["|"], []);
    integer count = llGetListLength(fields);
    scene = normalizeScene(scene);

    if (scene == "TRAFFIC")
    {
        if (count >= 4 && normalizeScene(llList2String(fields, 2)) == "TRAFFIC")
            return trim(llList2String(fields, 3));
        if (count >= 3) return trim(llList2String(fields, 2));
    }
    else if (count >= 3)
    {
        return trim(llList2String(fields, 2));
    }
    return "";
}

startBusy(string scene, string runId, integer fromBackend)
{
    busy = TRUE;
    busyScene = scene;
    busyRunId = runId;
    busyFromBackend = fromBackend;
    busyElapsed = 0.0;
    writePersistent("BUSY");
    updateHover();

    llOwnerSay("MASTER BUSY: " + scene + " | run=" + runId);
}

clearBusy()
{
    busy = FALSE;
    busyScene = "";
    busyRunId = "";
    busyFromBackend = FALSE;
    busyElapsed = 0.0;
    writePersistent("READY");
    updateHover();
}

queueSceneCommand(string scene, string command, integer startsRun, string runId, integer fromBackend)
{
    scene = normalizeScene(scene);
    if (scene == "")
    {
        llOwnerSay("MASTER ERROR: scene tidak valid.");
        return;
    }

    if (!initialized)
    {
        llOwnerSay("MASTER: tekan INIT sekali sebelum mengganti atau menjalankan scene.");
        return;
    }

    if (busy)
    {
        llOwnerSay("MASTER BUSY: tunggu animasi selesai atau gunakan ABORT.");
        return;
    }

    if (pendingCommand != "")
    {
        llOwnerSay("MASTER SWITCHING: tunggu pergantian scene selesai.");
        return;
    }

    pendingScene = scene;
    pendingCommand = command;
    pendingStartsRun = startsRun;
    pendingFromBackend = fromBackend;
    pendingRunId = runId;
    pendingElapsed = 0.0;

    if (activeScene != "" && activeScene != scene)
    {
        syncVisibility("");
        sendScene(activeScene, "HIDE");
        pendingDelay = SWITCH_DELAY;
    }
    else
    {
        pendingDelay = SAME_SCENE_DELAY;
    }

    updateHover();
}

selectScene(string scene)
{
    queueSceneCommand(scene, "SHOW", FALSE, "", FALSE);
}

abortAnimation()
{
    if (!busy)
    {
        llOwnerSay("MASTER ABORT: tidak ada animasi aktif.");
        return;
    }

    string oldScene = busyScene;
    string oldRun = busyRunId;
    sendScene(oldScene, "RESET");
    clearBusy();
    llOwnerSay("MASTER ABORTED: " + oldScene + " | run=" + oldRun);
}

status()
{
    string sceneText = activeScene;
    if (sceneText == "") sceneText = "NONE";

    string stateText = "READY";
    if (!initialized) stateText = "NOT_INITIALIZED";
    else if (busy) stateText = "BUSY";
    else if (pendingCommand != "") stateText = "SWITCHING";

    llOwnerSay(
        "MASTER STATUS: scene=" + sceneText
        + " | state=" + stateText
        + " | backend=" + backendStatus
        + " | attempt=" + backendAttempt
    );
}

initializeMaster()
{
    if (busy) abortAnimation();
    if (pendingCommand != "")
    {
        llOwnerSay("MASTER INIT DITOLAK: pergantian scene masih berlangsung.");
        return;
    }

    initialized = TRUE;

    if (activeScene == "")
    {
        hideOtherScenes("IDLE");
        pendingScene = "IDLE";
        pendingCommand = "SHOW";
        pendingStartsRun = FALSE;
        pendingFromBackend = FALSE;
        pendingRunId = "";
        pendingElapsed = 0.0;
        pendingDelay = SWITCH_DELAY;
        writePersistent("READY");
        updateHover();
        llOwnerSay("MASTER INIT: scene soal disembunyikan, lalu IDLE ditampilkan.");
        return;
    }

    queueSceneCommand("IDLE", "SHOW", FALSE, "", FALSE);
}

routeSimpleCommand(string command, string scene)
{
    command = upper(command);
    scene = normalizeScene(scene);
    if (scene == "") scene = activeScene;

    if (scene == "")
    {
        llOwnerSay("MASTER: belum ada scene aktif.");
        return;
    }

    if (command == "SHOW" || command == "EDIT" || command == "CALIBRATE")
    {
        queueSceneCommand(scene, command, FALSE, "", FALSE);
        return;
    }

    if (busy && command != "RESET")
    {
        llOwnerSay("MASTER BUSY: gunakan ABORT atau tunggu ANIMATION_DONE.");
        return;
    }

    if (command == "RESET")
    {
        if (busy) abortAnimation();
        else sendScene(scene, "RESET");
        return;
    }

    if (command == "HIDE")
    {
        sendScene(scene, "HIDE");
        if (scene == activeScene)
        {
            syncVisibility("");
            activeScene = "";
            writePersistent("READY");
            updateHover();
        }
        return;
    }

    if (command == "PLAY")
    {
        if (scene == "IDLE") sendScene(scene, "PLAY");
        else queueSceneCommand(scene, "PLAY", TRUE, "PLAY-" + (string)llGetUnixTime(), FALSE);
    }
}

routeResult(string message, integer fromBackend)
{
    if (busy)
    {
        llOwnerSay("MASTER BUSY: RESULT baru ditolak.");
        return;
    }

    if (startsWith(upper(message), "RESULT_SEQ|"))
    {
        list sequenceFields = llParseStringKeepNulls(message, ["|"], []);
        if (llGetListLength(sequenceFields) < 2)
        {
            llOwnerSay("MASTER RESULT_SEQ DITOLAK: format tidak valid.");
            return;
        }

        string sequenceRunId = trim(llList2String(sequenceFields, 1));
        if (sequenceRunId == "")
            sequenceRunId = "MASTER-" + (string)llGetUnixTime();

        queueSceneCommand("TRAFFIC", message, TRUE, sequenceRunId, fromBackend);
        return;
    }

    string scene = resultScene(message);
    if (scene == "" || scene == "IDLE")
    {
        llOwnerSay("MASTER RESULT DITOLAK: scene tidak valid.");
        return;
    }

    string runId = resultRunId(message, scene);
    if (runId == "") runId = "MASTER-" + (string)llGetUnixTime();
    queueSceneCommand(scene, message, TRUE, runId, fromBackend);
}

string sanitizeDisplay(string value)
{
    value = trim(value);
    value = llDumpList2String(llParseString2List(value, ["\n", "\r", ">", ",", "=", "|"], []), " ");
    while (llSubStringIndex(value, "  ") >= 0)
        value = llDumpList2String(llParseString2List(value, ["  "], []), " ");
    if (llStringLength(value) > 80) value = llGetSubString(value, 0, 79);
    if (value == "") value = "OUTPUT_TIDAK_VALID";
    return value;
}

string mapParkingEasy(list fields)
{
    string attempt = trim(llList2String(fields, 3));
    string vehicle = upper(llList2String(fields, 4));
    string displayValue = sanitizeDisplay(llList2String(fields, 6));

    string sequence =
        "VEHICLE=" + vehicle + ",ACTION=SHOW,AT=START"
        + ">ACTION=APPROACH,DIRECTION=EXIT"
        + ">ACTION=STOP"
        + ">DISPLAY=" + displayValue
        + ">BARRIER=OPEN"
        + ">ACTION=EXIT"
        + ">ACTION=HIDE"
        + ">BARRIER=CLOSE";

    return "RESULT|PARKING|" + attempt + "|" + sequence;
}

string mapParkingLoop(list fields)
{
    string attempt = trim(llList2String(fields, 3));
    string encoded = trim(llList2String(fields, 4));
    string total = sanitizeDisplay(llList2String(fields, 5));
    list vehicles = llParseStringKeepNulls(encoded, [";"], []);
    string sequence = "";
    integer i;

    for (i = 0; i < llGetListLength(vehicles); i++)
    {
        list pair = llParseStringKeepNulls(llList2String(vehicles, i), [","], []);
        if (llGetListLength(pair) >= 1)
        {
            string vehicle = upper(llList2String(pair, 0));
            string part =
                "VEHICLE=" + vehicle + ",ACTION=SHOW,AT=START"
                + ">ACTION=APPROACH,DIRECTION=EXIT"
                + ">ACTION=STOP"
                + ">BARRIER=OPEN"
                + ">ACTION=EXIT"
                + ">ACTION=HIDE"
                + ">BARRIER=CLOSE";
            if (sequence != "") sequence += ">";
            sequence += part;
        }
    }

    if (sequence != "") sequence += ">";
    sequence += "DISPLAY=" + total;
    return "RESULT|PARKING|" + attempt + "|" + sequence;
}

string mapPackage(list fields)
{
    string attempt = trim(llList2String(fields, 3));
    string inputText = trim(llList2String(fields, 4));
    string outputText = trim(llList2String(fields, 5));
    list sortedValues = llParseStringKeepNulls(outputText, [","], []);
    list inputValues;
    if (inputText == "") inputValues = sortedValues;
    else inputValues = llParseStringKeepNulls(inputText, [","], []);
    integer count = llGetListLength(inputValues);

    if (count < 1 || count > 5 || llGetListLength(sortedValues) != count) return "";

    list used = [];
    integer i;
    for (i = 0; i < count; i++) used += [0];

    string sequence = "";
    for (i = 0; i < count; i++)
    {
        string value = trim(llList2String(inputValues, i));
        integer slot = -1;
        integer j;
        for (j = 0; j < count && slot < 0; j++)
        {
            if (!llList2Integer(used, j) && trim(llList2String(sortedValues, j)) == value)
            {
                slot = j;
                used = llListReplaceList(used, [1], j, j);
            }
        }
        if (slot < 0) return "";

        string part =
            "PACKAGE=PACKAGE_" + (string)(i + 1) + ",ACTION=PICK"
            + ">ACTION=MOVE,TARGET=SLOT_" + (string)(slot + 1)
            + ">ACTION=DROP";
        if (sequence != "") sequence += ">";
        sequence += part;
    }

    return "RESULT|PACKAGE|" + attempt + "|" + sequence;
}

string mapRiver(list fields)
{
    string attempt = trim(llList2String(fields, 3));
    list actions = llParseStringKeepNulls(upper(llList2String(fields, 4)), [","], []);
    string direction = "RIGHT";
    string sequence = "";
    integer i;

    for (i = 0; i < llGetListLength(actions); i++)
    {
        string action = trim(llList2String(actions, i));
        if (action != "")
        {
            string loadValue = "GEMBALA";
            if (action != "SENDIRI") loadValue += "+" + action;

            string part = "LOAD=" + loadValue + ">BOAT=" + direction + ">UNLOAD=" + loadValue;
            if (sequence != "") sequence += ">";
            sequence += part;

            if (direction == "RIGHT") direction = "LEFT";
            else direction = "RIGHT";
        }
    }

    if (sequence == "") return "";
    sequence += ">SUCCESS=OK";
    return "RESULT|RIVER|" + attempt + "|" + sequence;
}

string mapRescue(list fields)
{
    string attempt = trim(llList2String(fields, 3));
    string path = upper(llList2String(fields, 5));
    string score = sanitizeDisplay(llList2String(fields, 6));
    string sequence = "";
    integer i;

    for (i = 0; i < llStringLength(path); i++)
    {
        string letter = llGetSubString(path, i, i);
        string move = "";
        if (letter == "U") move = "UP";
        else if (letter == "D") move = "DOWN";
        else if (letter == "L") move = "LEFT";
        else if (letter == "R") move = "RIGHT";

        if (move != "")
        {
            if (sequence != "") sequence += ">";
            sequence += "MOVE=" + move;
        }
    }

    if (sequence == "") return "";
    sequence += ">GOAL=" + score;
    return "RESULT|RESCUE|" + attempt + "|" + sequence;
}

string mapBackendResult(string body)
{
    if (startsWith(upper(body), "RESULT_SEQ|")) return body;

    list fields = llParseStringKeepNulls(body, ["|"], []);
    integer count = llGetListLength(fields);
    if (count < 4 || upper(llList2String(fields, 0)) != "RESULT") return "";

    if (normalizeScene(llList2String(fields, 1)) != "") return body;

    string question = upper(llList2String(fields, 1));
    string scene = normalizeScene(llList2String(fields, 2));

    if (scene == "TRAFFIC" && count >= 7) return body;
    if (question == "E02_PARKING" && count >= 7) return mapParkingEasy(fields);
    if (question == "M01_PARKING_LOOP" && count >= 6) return mapParkingLoop(fields);
    if (scene == "PACKAGE" && count >= 6) return mapPackage(fields);
    if (scene == "RIVER" && count >= 5) return mapRiver(fields);
    if (scene == "RESCUE" && count >= 7) return mapRescue(fields);

    return "";
}

openMonitor(string url)
{
    if (url != "" && url != currentPage)
    {
        currentPage = url;
        sendMasterEvent("OPEN_URL|" + url);
    }
}

applyBackendState(string body)
{
    list fields = llParseStringKeepNulls(body, ["|"], []);
    if (llGetListLength(fields) < 8 || upper(llList2String(fields, 0)) != "STATE") return;

    integer version = (integer)llList2String(fields, 1);
    backendStatus = upper(llList2String(fields, 2));
    backendScene = normalizeScene(llList2String(fields, 5));
    backendAttempt = trim(llList2String(fields, 6));
    string pageUrl = trim(llList2String(fields, 7));

    openMonitor(pageUrl);
    updateHover();

    if (version == lastStateVersion) return;
    lastStateVersion = version;

    if (!initialized) return;
    if (busy || pendingCommand != "") return;

    string target = backendScene;
    if (backendStatus == "IDLE" || backendStatus == "SELECT_LEVEL" || backendStatus == "SELECT_QUESTION")
        target = "IDLE";

    if (target != "" && target != activeScene)
        queueSceneCommand(target, "SHOW", FALSE, "", FALSE);
}

requestStationState()
{
    if (requestState != NULL_KEY) return;
    requestState = llHTTPRequest(
        API_BASE + "/api/station/state",
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

startSession(string avatarId, string avatarName)
{
    requestStart = llHTTPRequest(
        API_BASE + "/api/station/start?avatar_uuid=" + llEscapeURL(avatarId)
        + "&avatar_name=" + llEscapeURL(avatarName),
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

playBackendResult()
{
    if (requestPlay != NULL_KEY || busy || pendingCommand != "") return;
    requestPlay = llHTTPRequest(
        API_BASE + "/api/station/play",
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

resetBackendScene()
{
    if (requestReset != NULL_KEY) return;
    requestReset = llHTTPRequest(
        API_BASE + "/api/station/reset",
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

newBackendQuestion()
{
    if (requestNew != NULL_KEY) return;
    requestNew = llHTTPRequest(
        API_BASE + "/api/station/new-question",
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

finishBackendAnimation(string animationRunId)
{
    if (animationRunId == "" || requestFinish != NULL_KEY) return;
    requestFinish = llHTTPRequest(
        API_BASE + "/api/animation/ack?message="
        + llEscapeURL("ANIMATION_DONE|" + animationRunId),
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

homeBackendStation()
{
    if (requestHome != NULL_KEY) return;
    requestHome = llHTTPRequest(
        API_BASE + "/api/station/home",
        [HTTP_METHOD, "GET", HTTP_MIMETYPE, "text/plain"],
        ""
    );
}

handleCompletion(string message)
{
    if (!busy) return;

    list fields = llParseStringKeepNulls(message, ["|"], []);
    string completionRun = "";
    if (llGetListLength(fields) >= 2)
        completionRun = trim(llList2String(fields, llGetListLength(fields) - 1));

    if (busyRunId != "" && completionRun != "" && completionRun != busyRunId)
    {
        llOwnerSay("MASTER: ANIMATION_DONE lama diabaikan: " + completionRun);
        return;
    }

    string completedScene = busyScene;
    string completedRun = busyRunId;
    integer callBackend = busyFromBackend;
    clearBusy();

    llOwnerSay("MASTER DONE: " + completedScene + " | run=" + completedRun);
    if (callBackend) finishBackendAnimation(completedRun);
}

handleMasterCommand(string message)
{
    string raw = trim(message);
    string command = upper(raw);
    if (raw == "") return;

    if (startsWith(command, "ANIMATION_DONE|"))
    {
        handleCompletion(raw);
        return;
    }

    if (startsWith(command, "MASTER_") || startsWith(command, "OPEN_URL|")) return;

    if (command == "MENU")
    {
        openMainDialog(llGetOwner());
        return;
    }

    if (command == "MONITOR_READY")
    {
        currentPage = "";
        lastStateVersion = -1;
        requestStationState();
        return;
    }

    if (startsWith(command, "BTN_START|"))
    {
        list parts = llParseStringKeepNulls(raw, ["|"], []);
        startSession(llList2String(parts, 1), llList2String(parts, 2));
        return;
    }
    if (command == "BTN_PLAY") { playBackendResult(); return; }
    if (command == "BTN_RESET") { resetBackendScene(); return; }
    if (command == "BTN_NEW") { newBackendQuestion(); return; }
    if (command == "BTN_HOME") { homeBackendStation(); return; }

    if (startsWith(command, "RESULT|") || startsWith(command, "RESULT_SEQ|"))
    {
        routeResult(raw, FALSE);
        return;
    }

    list fields = llParseStringKeepNulls(raw, ["|"], []);
    string action = upper(llList2String(fields, 0));
    string scene = "";
    if (llGetListLength(fields) >= 2) scene = normalizeScene(llList2String(fields, 1));

    if (action == "INIT") initializeMaster();
    else if (action == "STATUS") status();
    else if (action == "ABORT") abortAnimation();
    else if (action == "HIDE_ALL" || action == "HIDE ALL") hideAllScenes();
    else if (action == "SCENE" || action == "SELECT") selectScene(scene);
    else if (action == "IDLE" || action == "TRAFFIC" || action == "PARKING"
        || action == "PACKAGE" || action == "RIVER" || action == "RESCUE") selectScene(action);
    else if (action == "EDIT" || action == "CALIBRATE" || action == "SHOW"
        || action == "RESET" || action == "HIDE" || action == "PLAY") routeSimpleCommand(action, scene);
    else llOwnerSay("MASTER COMMAND TIDAK DIKENAL: " + raw);
}

default
{
    state_entry()
    {
        if (masterListen) llListenRemove(masterListen);
        masterListen = llListen(MASTER_CHANNEL, "", NULL_KEY, "");

        dialogChannel = -700000 - (integer)llFrand(200000.0);
        closeDialog();
        hideMasterVisual();
        readPersistent();

        if (activeScene != "" && persistentMode == "BUSY")
        {
            sendScene(activeScene, "RESET");
            busy = FALSE;
            persistentMode = "READY";
            writePersistent("READY");
            llOwnerSay("MASTER RECOVERY: animasi sebelumnya dibatalkan.");
        }

        if (initialized && activeScene != "")
            syncVisibility(activeScene);
        else
            syncVisibility("");

        llSetTimerEvent(TIMER_STEP);
        pollElapsed = POLL_INTERVAL;
        updateHover();

        if (!initialized)
            llOwnerSay("SIMULATOR MASTER HTTP V1.5 READY. Tekan INIT sekali.");
        else
            llOwnerSay("SIMULATOR MASTER HTTP V1.5 READY. Backend polling dan visibility bus aktif.");
    }

    touch_start(integer totalNumber)
    {
        key user = llDetectedKey(0);
        if (user != llGetOwner()) return;
        openMainDialog(user);
    }

    listen(integer channel, string name, key speaker, string message)
    {
        if (channel == MASTER_CHANNEL)
        {
            if (!isOwnerSpeaker(speaker)) return;
            handleMasterCommand(message);
            return;
        }

        if (channel != dialogChannel || speaker != dialogUser || speaker != llGetOwner()) return;

        string button = upper(message);
        closeDialog();

        if (button == "TOOLS") openToolsDialog(speaker);
        else if (button == "BACK") openMainDialog(speaker);
        else if (button == "STATUS") { status(); openMainDialog(speaker); }
        else if (button == "HIDE ALL") hideAllScenes();
        else if (button == "INIT") initializeMaster();
        else if (button == "ABORT") abortAnimation();
        else if (button == "RESET" || button == "EDIT" || button == "CALIBRATE"
            || button == "SHOW" || button == "PLAY" || button == "HIDE") routeSimpleCommand(button, activeScene);
        else
        {
            string scene = normalizeScene(button);
            if (scene != "") selectScene(scene);
        }
    }

    timer()
    {
        pollElapsed += TIMER_STEP;
        if (pollElapsed >= POLL_INTERVAL)
        {
            pollElapsed = 0.0;
            requestStationState();
        }

        if (pendingCommand != "")
        {
            pendingElapsed += TIMER_STEP;
            if (pendingElapsed >= pendingDelay)
            {
                string scene = pendingScene;
                string command = pendingCommand;
                integer startsRun = pendingStartsRun;
                integer fromBackend = pendingFromBackend;
                string runId = pendingRunId;

                pendingScene = "";
                pendingCommand = "";
                pendingStartsRun = FALSE;
                pendingFromBackend = FALSE;
                pendingRunId = "";
                pendingElapsed = 0.0;

                if (upper(command) != "HIDE")
                    syncVisibility(scene);

                sendScene(scene, command);
                activeScene = scene;

                if (startsRun)
                {
                    if (runId == "") runId = "PLAY-" + (string)llGetUnixTime();
                    startBusy(scene, runId, fromBackend);
                }
                else
                {
                    writePersistent("READY");
                    updateHover();
                    llOwnerSay("MASTER ACTIVE: " + scene + " | command=" + command);
                }
            }
        }

        if (busy)
        {
            busyElapsed += TIMER_STEP;
            if (busyElapsed >= RUN_TIMEOUT)
            {
                string timeoutScene = busyScene;
                string timeoutRun = busyRunId;
                sendScene(timeoutScene, "RESET");
                clearBusy();
                llOwnerSay("MASTER TIMEOUT: " + timeoutScene + " | run=" + timeoutRun);
            }
        }
    }

    http_response(key requestId, integer statusCode, list metadata, string body)
    {
        integer isStart = requestId == requestStart;
        integer isState = requestId == requestState;
        integer isPlay = requestId == requestPlay;
        integer isReset = requestId == requestReset;
        integer isNew = requestId == requestNew;
        integer isFinish = requestId == requestFinish;
        integer isHome = requestId == requestHome;

        if (isStart) requestStart = NULL_KEY;
        if (isState) requestState = NULL_KEY;
        if (isPlay) requestPlay = NULL_KEY;
        if (isReset) requestReset = NULL_KEY;
        if (isNew) requestNew = NULL_KEY;
        if (isFinish) requestFinish = NULL_KEY;
        if (isHome) requestHome = NULL_KEY;

        if (statusCode < 200 || statusCode >= 300)
        {
            backendStatus = "HTTP_" + (string)statusCode;
            updateHover();
            llOwnerSay("BACKEND HTTP ERROR: " + (string)statusCode + " | " + body);
            return;
        }

        if (isFinish)
        {
            lastStateVersion = -1;
            requestStationState();
            return;
        }

        if (isState || isStart || isHome)
        {
            applyBackendState(body);
            return;
        }

        if (isPlay)
        {
            if (startsWith(upper(body), "ERROR|"))
            {
                llOwnerSay("BACKEND PLAY DITOLAK: " + body);
                return;
            }

            string mapped = mapBackendResult(body);
            if (mapped == "")
            {
                llOwnerSay("MASTER MAPPER ERROR: RESULT backend belum didukung: " + body);
                return;
            }
            routeResult(mapped, TRUE);
            return;
        }

        if (isReset)
        {
            list parts = llParseStringKeepNulls(body, ["|"], []);
            string scene = "";
            if (llGetListLength(parts) >= 3) scene = normalizeScene(llList2String(parts, 2));
            if (scene == "") scene = activeScene;
            if (scene != "")
            {
                if (scene == activeScene) sendScene(scene, "RESET");
                else queueSceneCommand(scene, "RESET", FALSE, "", FALSE);
            }
            return;
        }

        if (isNew)
        {
            list parts = llParseStringKeepNulls(body, ["|"], []);
            if (upper(llList2String(parts, 0)) == "NEW")
            {
                string scene = normalizeScene(llList2String(parts, 2));
                string pageUrl = llList2String(parts, 4);
                backendAttempt = llList2String(parts, 3);
                openMonitor(pageUrl);
                lastStateVersion = -1;
                if (scene != "" && scene != activeScene)
                    queueSceneCommand(scene, "SHOW", FALSE, "", FALSE);
                else if (scene != "") sendScene(scene, "RESET");
            }
            else llOwnerSay("BACKEND NEW DITOLAK: " + body);
        }
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
        else if (change & (CHANGED_LINK | CHANGED_SHAPE | CHANGED_TEXTURE)) hideMasterVisual();
    }
}

