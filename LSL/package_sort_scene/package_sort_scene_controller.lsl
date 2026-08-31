// Package-sort scene controller: coordinate actors and backend animation events.
integer MASTER_CHANNEL = -451200;
integer SCENE_CHANNEL = -451232;
integer VISIBILITY_CHANNEL = -451299;

string STATE_VERSION = "PACKAGE_V4_GROUP_RESTORE";
float HIDE_OFFSET = 1000.0;
float TIMER_STEP = 0.05;
float MOVE_DURATION = 0.65;
float PICK_HEIGHT = 0.18;
integer MAX_STEPS = 40;
integer MAX_RESULT_CHARS = 1200;

integer sceneListen = 0;
integer visibilityListen = 0;
integer visible = TRUE;
vector rootHome = ZERO_VECTOR;
integer rootHomeValid = FALSE;

list sequenceSteps = [];
integer sequenceIndex = 0;
integer sequenceRunning = FALSE;
string activeRunId = "";
string lastResult = "";

integer moving = FALSE;
float moveElapsed = 0.0;
list movingLinks = [];
list movingStartPositions = [];
list movingTargetPositions = [];
list movingRotations = [];

string trim(string value) { return llStringTrim(value, STRING_TRIM); }
string upper(string value) { return llToUpper(trim(value)); }
string lower(string value) { return llToLower(trim(value)); }
integer startsWith(string value, string prefix) { return llSubStringIndex(value, prefix) == 0; }
integer ownerSpeaker(key speaker) { return llGetOwnerKey(speaker) == llGetOwner(); }

integer packageIndexFromId(string packageId)
{
    packageId = upper(packageId);
    if (packageId == "PACKAGE_1") return 1;
    if (packageId == "PACKAGE_2") return 2;
    if (packageId == "PACKAGE_3") return 3;
    if (packageId == "PACKAGE_4") return 4;
    if (packageId == "PACKAGE_5") return 5;
    return 0;
}

integer packageNameMatches(string name, integer packageIndex)
{
    name = lower(name);
    string base = "package_" + (string)packageIndex;
    if (name == base) return TRUE;
    if (!startsWith(name, base)) return FALSE;

    integer baseLength = llStringLength(base);
    if (llStringLength(name) <= baseLength) return TRUE;

    string boundary = llGetSubString(name, baseLength, baseLength);
    if (boundary == "#") return TRUE;
    if (boundary == "_") return TRUE;
    if (boundary == ".") return TRUE;
    if (boundary == "-") return TRUE;
    if (boundary == " ") return TRUE;
    return FALSE;
}

integer findExact(string target)
{
    target = lower(target);
    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
    {
        if (lower(llGetLinkName(link)) == target) return link;
    }
    return 0;
}

list packageLinks(integer packageIndex)
{
    list result = [];
    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
    {
        if (packageNameMatches(llGetLinkName(link), packageIndex)) result += [link];
    }
    return result;
}

integer packageAnchor(integer packageIndex)
{
    integer exact = findExact("package_" + (string)packageIndex);
    if (exact) return exact;
    list links = packageLinks(packageIndex);
    if (llGetListLength(links)) return llList2Integer(links, 0);
    return 0;
}

vector localPos(integer link)
{
    return llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL]), 0);
}

rotation localRot(integer link)
{
    return llList2Rot(llGetLinkPrimitiveParams(link, [PRIM_ROT_LOCAL]), 0);
}

string homeDescription(vector positionValue, rotation rotationValue)
{
    return "PACKAGE_HOME|" + STATE_VERSION + "|" + (string)positionValue + "|" + (string)rotationValue;
}

captureRootHome()
{
    rootHome = llGetPos();
    rootHomeValid = TRUE;
    llSetObjectDesc("PACKAGE_ROOT|" + STATE_VERSION + "|" + (string)rootHome);
}

loadRootHome()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    if (llGetListLength(fields) >= 3 && upper(llList2String(fields, 0)) == "PACKAGE_ROOT")
    {
        rootHome = (vector)llList2String(fields, 2);
        rootHomeValid = TRUE;
    }
    else captureRootHome();
}

capturePackageHomes()
{
    integer packageIndex;
    for (packageIndex = 1; packageIndex <= 5; packageIndex++)
    {
        list links = packageLinks(packageIndex);
        integer i;
        for (i = 0; i < llGetListLength(links); i++)
        {
            integer link = llList2Integer(links, i);
            vector positionValue = localPos(link);
            rotation rotationValue = localRot(link);
            llSetLinkPrimitiveParamsFast(link, [PRIM_DESC, homeDescription(positionValue, rotationValue)]);
        }
    }
    llOwnerSay("PACKAGE V4 CALIBRATED: HOME seluruh grup package dan root disimpan.");
}

integer restoreOnePackage(integer packageIndex)
{
    list links = packageLinks(packageIndex);
    if (!llGetListLength(links)) return FALSE;
    list rules = [];
    integer i;
    for (i = 0; i < llGetListLength(links); i++)
    {
        integer link = llList2Integer(links, i);
        string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
        list fields = llParseStringKeepNulls(description, ["|"], []);
        if (llGetListLength(fields) < 4 || upper(llList2String(fields, 0)) != "PACKAGE_HOME") return FALSE;
        vector positionValue = (vector)llList2String(fields, 2);
        rotation rotationValue = (rotation)llList2String(fields, 3);
        rules += [PRIM_LINK_TARGET, link, PRIM_POS_LOCAL, positionValue, PRIM_ROT_LOCAL, rotationValue, PRIM_GLOW, ALL_SIDES, 0.0];
    }
    if (llGetListLength(rules)) llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
    return TRUE;
}

clearLabels()
{
    integer packageIndex;
    for (packageIndex = 1; packageIndex <= 5; packageIndex++)
    {
        integer anchor = packageAnchor(packageIndex);
        if (anchor) llSetLinkPrimitiveParamsFast(anchor, [PRIM_TEXT, "", <1.0, 1.0, 1.0>, 0.0]);
    }
}

resetPackages()
{
    integer packageIndex;
    for (packageIndex = 1; packageIndex <= 5; packageIndex++) restoreOnePackage(packageIndex);
    clearLabels();
}

stopSequence()
{
    sequenceRunning = FALSE;
    moving = FALSE;
    sequenceSteps = [];
    sequenceIndex = 0;
    activeRunId = "";
    llSetTimerEvent(0.0);
}

showScene()
{
    stopSequence();
    if (!rootHomeValid) loadRootHome();
    llSetRegionPos(rootHome);
    visible = TRUE;
    resetPackages();
}

hideScene()
{
    stopSequence();
    resetPackages();
    if (!rootHomeValid) loadRootHome();
    llSetRegionPos(rootHome + <0.0, 0.0, HIDE_OFFSET>);
    visible = FALSE;
}

setPackageLabel(integer packageIndex, string encodedText)
{
    integer anchor = packageAnchor(packageIndex);
    if (!anchor) return;
    string labelText = llUnescapeURL(encodedText);
    if (llStringLength(labelText) > 80) labelText = llGetSubString(labelText, 0, 79);
    llSetLinkPrimitiveParamsFast(anchor, [PRIM_TEXT, labelText, <0.05, 0.15, 0.35>, 1.0]);
}

highlightPackage(integer packageIndex)
{
    list links = packageLinks(packageIndex);
    integer i;
    for (i = 0; i < llGetListLength(links); i++)
    {
        llSetLinkPrimitiveParamsFast(llList2Integer(links, i), [PRIM_GLOW, ALL_SIDES, 0.08]);
    }
}

startPackageMove(integer packageIndex, vector delta)
{
    movingLinks = packageLinks(packageIndex);
    movingStartPositions = [];
    movingTargetPositions = [];
    movingRotations = [];
    integer i;
    for (i = 0; i < llGetListLength(movingLinks); i++)
    {
        integer link = llList2Integer(movingLinks, i);
        vector startPosition = localPos(link);
        movingStartPositions += [startPosition];
        movingTargetPositions += [startPosition + delta];
        movingRotations += [localRot(link)];
    }
    moveElapsed = 0.0;
    moving = llGetListLength(movingLinks) > 0;
    if (moving) llSetTimerEvent(TIMER_STEP);
}

movePackageToSlot(integer packageIndex, integer slotIndex)
{
    integer anchor = packageAnchor(packageIndex);
    integer slotLink = findExact("slot_" + (string)slotIndex);
    if (!anchor || !slotLink)
    {
        llOwnerSay("PACKAGE V4 ERROR: package atau slot tidak ditemukan.");
        stopSequence();
        return;
    }
    vector targetPosition = localPos(slotLink) + <0.0, 0.0, PICK_HEIGHT>;
    startPackageMove(packageIndex, targetPosition - localPos(anchor));
}

applyMovement(float progress)
{
    list rules = [];
    integer i;
    for (i = 0; i < llGetListLength(movingLinks); i++)
    {
        vector startPosition = llList2Vector(movingStartPositions, i);
        vector targetPosition = llList2Vector(movingTargetPositions, i);
        vector positionValue = startPosition + ((targetPosition - startPosition) * progress);
        rules += [PRIM_LINK_TARGET, llList2Integer(movingLinks, i), PRIM_POS_LOCAL, positionValue, PRIM_ROT_LOCAL, llList2Rot(movingRotations, i)];
    }
    if (llGetListLength(rules)) llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
}

integer validRunId(string value)
{
    if (value == "") return FALSE;
    if (llSubStringIndex(value, "|") >= 0) return FALSE;
    if (llSubStringIndex(value, ">") >= 0) return FALSE;
    if (llSubStringIndex(value, "=") >= 0) return FALSE;
    if (llSubStringIndex(value, ",") >= 0) return FALSE;
    return TRUE;
}

integer terminalStep(string step)
{
    return FALSE;
}

runNext()
{
    if (!sequenceRunning || moving) return;
    if (sequenceIndex >= llGetListLength(sequenceSteps))
    {
        string completedRun = activeRunId;
        sequenceRunning = FALSE;
        activeRunId = "";
        llSetTimerEvent(0.0);
        llRegionSay(MASTER_CHANNEL, "ANIMATION_DONE|" + completedRun);
        llOwnerSay("PACKAGE V4 SELESAI: run=" + completedRun + ".");
        return;
    }

    string step = trim(llList2String(sequenceSteps, sequenceIndex));
    sequenceIndex++;

    if (step == "LABEL_CLEAR=ALL")
    {
        clearLabels();
        runNext();
        return;
    }
    if (startsWith(upper(step), "LABEL="))
    {
        list parts = llParseStringKeepNulls(step, [","], []);
        string packageId = llGetSubString(llList2String(parts, 0), 6, -1);
        string encodedText = "";
        if (llGetListLength(parts) >= 2 && startsWith(upper(llList2String(parts, 1)), "TEXT="))
            encodedText = llGetSubString(llList2String(parts, 1), 5, -1);
        integer packageIndex = packageIndexFromId(packageId);
        if (!packageIndex || encodedText == "")
        {
            llOwnerSay("PACKAGE V4 ERROR: LABEL tidak valid.");
            stopSequence();
            return;
        }
        setPackageLabel(packageIndex, encodedText);
        runNext();
        return;
    }
    if (startsWith(upper(step), "HIGHLIGHT="))
    {
        integer packageIndex = packageIndexFromId(llGetSubString(step, 10, -1));
        if (!packageIndex)
        {
            stopSequence();
            return;
        }
        highlightPackage(packageIndex);
        runNext();
        return;
    }
    if (startsWith(upper(step), "PACKAGE="))
    {
        list parts = llParseStringKeepNulls(step, [","], []);
        string packageId = llGetSubString(llList2String(parts, 0), 8, -1);
        integer packageIndex = packageIndexFromId(packageId);
        string action = "";
        string target = "";
        integer i;
        for (i = 1; i < llGetListLength(parts); i++)
        {
            string part = trim(llList2String(parts, i));
            if (startsWith(upper(part), "ACTION=")) action = upper(llGetSubString(part, 7, -1));
            else if (startsWith(upper(part), "TARGET=")) target = upper(llGetSubString(part, 7, -1));
        }
        if (!packageIndex)
        {
            stopSequence();
            return;
        }
        if (action == "PICK")
        {
            startPackageMove(packageIndex, <0.0, 0.0, PICK_HEIGHT>);
            return;
        }
        if (action == "MOVE")
        {
            integer slotIndex = 0;
            if (target == "SLOT_1") slotIndex = 1;
            else if (target == "SLOT_2") slotIndex = 2;
            else if (target == "SLOT_3") slotIndex = 3;
            else if (target == "SLOT_4") slotIndex = 4;
            else if (target == "SLOT_5") slotIndex = 5;
            if (!slotIndex)
            {
                stopSequence();
                return;
            }
            movePackageToSlot(packageIndex, slotIndex);
            return;
        }
        if (action == "DROP")
        {
            startPackageMove(packageIndex, <0.0, 0.0, -PICK_HEIGHT>);
            return;
        }
    }

    llOwnerSay("PACKAGE V4 ERROR: action tidak dikenal: " + step);
    stopSequence();
}

integer validateSequence(list steps)
{
    if (llGetListLength(steps) < 2 || llGetListLength(steps) > MAX_STEPS) return FALSE;
    integer movementSeen = FALSE;
    integer labelSeen = FALSE;
    integer i;
    for (i = 0; i < llGetListLength(steps); i++)
    {
        string step = trim(llList2String(steps, i));
        string command = upper(step);
        if (step == "") return FALSE;
        if (command == "LABEL_CLEAR=ALL")
        {
            if (movementSeen) return FALSE;
        }
        else if (startsWith(command, "LABEL="))
        {
            if (movementSeen) return FALSE;
            labelSeen = TRUE;
        }
        else if (startsWith(command, "HIGHLIGHT=") || startsWith(command, "PACKAGE=")) movementSeen = TRUE;
        else return FALSE;
    }
    return labelSeen;
}

handleResult(string message)
{
    if (llStringLength(message) > MAX_RESULT_CHARS)
    {
        llOwnerSay("PACKAGE V4 RESULT ditolak: payload terlalu panjang.");
        return;
    }
    list fields = llParseStringKeepNulls(message, ["|"], []);
    if (llGetListLength(fields) != 4 || upper(llList2String(fields, 0)) != "RESULT" || upper(llList2String(fields, 1)) != "PACKAGE") return;
    string runId = trim(llList2String(fields, 2));
    list steps = llParseStringKeepNulls(llList2String(fields, 3), [">"], []);
    if (!validRunId(runId) || !validateSequence(steps))
    {
        llOwnerSay("PACKAGE V4 RESULT ditolak: format atau sequence tidak valid.");
        return;
    }

    stopSequence();
    if (!rootHomeValid) loadRootHome();
    llSetRegionPos(rootHome);
    visible = TRUE;
    resetPackages();
    activeRunId = runId;
    sequenceSteps = steps;
    sequenceIndex = 0;
    sequenceRunning = TRUE;
    lastResult = message;
    runNext();
}

integer packageGroupCount(integer packageIndex)
{
    return llGetListLength(packageLinks(packageIndex));
}

reportPackageLinks()
{
    integer packageIndex;
    for (packageIndex = 1; packageIndex <= 5; packageIndex++)
    {
        list links = packageLinks(packageIndex);
        string summary = "";
        integer i;
        for (i = 0; i < llGetListLength(links); i++)
        {
            integer link = llList2Integer(links, i);
            if (summary != "") summary += ", ";
            summary += (string)link + ":" + llGetLinkName(link);
        }
        llOwnerSay("PACKAGE V4 LINKS P" + (string)packageIndex + "=" + (string)llGetListLength(links) + " [" + summary + "]");
    }
}

status()
{
    llOwnerSay(
        "PACKAGE V4 STATUS: visible=" + (string)visible
        + ", running=" + (string)sequenceRunning
        + ", run=" + activeRunId
        + ", packages=" + (string)(packageAnchor(1) > 0) + (string)(packageAnchor(2) > 0)
        + (string)(packageAnchor(3) > 0) + (string)(packageAnchor(4) > 0) + (string)(packageAnchor(5) > 0)
        + ", groupLinks=" + (string)packageGroupCount(1) + "," + (string)packageGroupCount(2)
        + "," + (string)packageGroupCount(3) + "," + (string)packageGroupCount(4)
        + "," + (string)packageGroupCount(5)
    );
}

default
{
    state_entry()
    {
        if (sceneListen) llListenRemove(sceneListen);
        if (visibilityListen) llListenRemove(visibilityListen);
        sceneListen = llListen(SCENE_CHANNEL, "", NULL_KEY, "");
        visibilityListen = llListen(VISIBILITY_CHANNEL, "", NULL_KEY, "");
        loadRootHome();
        integer needCalibration = FALSE;
        integer packageIndex;
        for (packageIndex = 1; packageIndex <= 5; packageIndex++)
        {
            integer anchor = packageAnchor(packageIndex);
            if (!anchor) needCalibration = TRUE;
            else
            {
                string description = llList2String(llGetLinkPrimitiveParams(anchor, [PRIM_DESC]), 0);
                if (!startsWith(upper(description), "PACKAGE_HOME|")) needCalibration = TRUE;
            }
        }
        if (needCalibration) capturePackageHomes();
        resetPackages();
        llOwnerSay("PACKAGE SCENE V4 READY: dynamic labels dan group movement aktif pada channel -451232.");
    }

    listen(integer channel, string name, key speaker, string message)
    {
        if (!ownerSpeaker(speaker)) return;
        string command = upper(message);
        if (channel == VISIBILITY_CHANNEL)
        {
            if (command == "HIDE_ALL") hideScene();
            else if (command == "SHOW_ONLY|PACKAGE" || command == "SHOW_ONLY|PACKAGE_SORT") showScene();
            else if (startsWith(command, "SHOW_ONLY|")) hideScene();
            return;
        }
        if (channel != SCENE_CHANNEL) return;
        if (startsWith(command, "RESULT|PACKAGE|")) handleResult(message);
        else if (command == "SHOW") showScene();
        else if (command == "HIDE") hideScene();
        else if (command == "RESET" || command == "EDIT")
        {
            stopSequence();
            if (!rootHomeValid) loadRootHome();
            llSetRegionPos(rootHome);
            visible = TRUE;
            resetPackages();
        }
        else if (command == "CALIBRATE")
        {
            stopSequence();
            captureRootHome();
            capturePackageHomes();
            resetPackages();
        }
        else if (command == "PLAY")
        {
            if (lastResult != "") handleResult(lastResult);
        }
        else if (command == "STATUS") status();
        else if (command == "LINKS") reportPackageLinks();
    }

    timer()
    {
        if (!moving)
        {
            llSetTimerEvent(0.0);
            return;
        }
        moveElapsed += TIMER_STEP;
        float progress = moveElapsed / MOVE_DURATION;
        if (progress > 1.0) progress = 1.0;
        applyMovement(progress);
        if (progress >= 1.0)
        {
            moving = FALSE;
            llSetTimerEvent(0.0);
            runNext();
        }
    }

    on_rez(integer startParameter) { llResetScript(); }
    changed(integer change)
    {
        if (change & (CHANGED_OWNER | CHANGED_LINK)) llResetScript();
    }
}
