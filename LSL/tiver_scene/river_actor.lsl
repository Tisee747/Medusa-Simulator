// River actor: animate the validated river-crossing state transitions.
integer MSG_EDIT = 9701;
integer MSG_CALIBRATE = 9702;
integer MSG_SHOW = 9703;
integer MSG_RESET = 9704;
integer MSG_HIDE = 9705;
integer MSG_ACTION = 9710;
integer MSG_ACTION_DONE = 9711;

string STATE_VERSION = "RIVER_V1";
float TIMER_STEP = 0.04;
float BOAT_MOVE_SPEED = 1.45;
float BOAT_MIN_DURATION = 2.20;
float BOAT_MAX_DURATION = 5.50;
float BOAT_TURN_DURATION = 0.65;
float LOAD_DURATION = 0.55;
float INVALID_DURATION = 0.40;
integer BATCH_SIZE = 8;

list actorLinks = [];
list actorGroups = [];
list homePositions = [];
list homeRotations = [];
list groupNames = ["GEMBALA", "SERIGALA", "DOMBA", "RUMPUT", "BOAT"];
list anchorLinks = [];
list leftMarkers = [];
list rightMarkers = [];
integer boatLeftMarker = 0;
integer boatRightMarker = 0;
integer ready = FALSE;

list onboard = [];
string currentSide = "LEFT";
string boatFacing = "RIGHT";

list moveLinks = [];
list moveStartPositions = [];
list moveStartRotations = [];
list moveTargetPositions = [];
list moveTargetRotations = [];
float moveElapsed = 0.0;
float moveDuration = 0.5;
integer moving = FALSE;
string actionName = "";
string pendingSide = "";
list pendingAdd = [];
list pendingRemove = [];
integer statusTimer = FALSE;

integer queuedBoatTravel = FALSE;
string queuedBoatSide = "";
vector queuedBoatTarget = ZERO_VECTOR;


rotation normalizeRotation(rotation value)
{
    float magnitude = llSqrt(
        (value.x * value.x)
        + (value.y * value.y)
        + (value.z * value.z)
        + (value.s * value.s)
    );

    if (magnitude <= 0.000001)
    {
        return ZERO_ROTATION;
    }

    return <
        value.x / magnitude,
        value.y / magnitude,
        value.z / magnitude,
        value.s / magnitude
    >;
}

rotation rotationLerp(rotation startRot, rotation targetRot, float amount)
{
    float dot =
        (startRot.x * targetRot.x)
        + (startRot.y * targetRot.y)
        + (startRot.z * targetRot.z)
        + (startRot.s * targetRot.s);

    if (dot < 0.0)
    {
        targetRot = <-targetRot.x, -targetRot.y, -targetRot.z, -targetRot.s>;
    }

    rotation result = <
        startRot.x + ((targetRot.x - startRot.x) * amount),
        startRot.y + ((targetRot.y - startRot.y) * amount),
        startRot.z + ((targetRot.z - startRot.z) * amount),
        startRot.s + ((targetRot.s - startRot.s) * amount)
    >;

    return normalizeRotation(result);
}

string lower(string value) { return llToLower(llStringTrim(value, STRING_TRIM)); }
string upper(string value) { return llToUpper(llStringTrim(value, STRING_TRIM)); }
integer startsWith(string value, string prefix) { return llSubStringIndex(value, prefix) == 0; }

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

vector localPos(integer link)
{
    return llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL]), 0);
}

rotation localRot(integer link)
{
    return llList2Rot(llGetLinkPrimitiveParams(link, [PRIM_ROT_LOCAL]), 0);
}

string rootMode()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);
    if (llGetListLength(fields) < 5) return "RECOVERY";
    if (upper(llList2String(fields, 0)) != "HOME") return "RECOVERY";
    if (upper(llList2String(fields, 1)) != STATE_VERSION) return "RECOVERY";
    return upper(llList2String(fields, 4));
}

integer groupIndex(string value)
{
    return llListFindList(groupNames, [upper(value)]);
}

integer memberOf(string name, string base)
{
    name = lower(name);
    base = lower(base);
    if (name == base) return TRUE;
    if (startsWith(name, base + "#")) return TRUE;
    if (startsWith(name, base + "__#")) return TRUE;
    return FALSE;
}

integer discover()
{
    actorLinks = [];
    actorGroups = [];
    anchorLinks = [];
    leftMarkers = [];
    rightMarkers = [];

    list bases = ["gembala", "serigala", "domba", "rumput", "boat"];
    integer i;
    for (i = 0; i < 5; i++)
    {
        integer anchor = findExact(llList2String(bases, i));
        if (!anchor)
        {
            llOwnerSay("RIVER ERROR: anchor " + llList2String(bases, i) + " tidak ditemukan.");
            return FALSE;
        }
        anchorLinks += [anchor];
    }

    leftMarkers = [
        findExact("left_gembala"),
        findExact("left_serigala"),
        findExact("left_domba"),
        findExact("left_rumput")
    ];
    rightMarkers = [
        findExact("right_gembala"),
        findExact("right_serigala"),
        findExact("right_domba"),
        findExact("right_rumput")
    ];
    boatLeftMarker = findExact("boat_left");
    boatRightMarker = findExact("boat_right");

    for (i = 0; i < 4; i++)
    {
        if (!llList2Integer(leftMarkers, i) || !llList2Integer(rightMarkers, i))
        {
            llOwnerSay("RIVER ERROR: marker actor tidak lengkap.");
            return FALSE;
        }
    }

    if (!boatLeftMarker || !boatRightMarker)
    {
        llOwnerSay("RIVER ERROR: boat_left atau boat_right tidak ditemukan.");
        return FALSE;
    }

    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
    {
        string name = llGetLinkName(link);
        integer group = -1;
        for (i = 0; i < 5; i++)
        {
            if (memberOf(name, llList2String(bases, i))) group = i;
        }
        if (group >= 0)
        {
            actorLinks += [link];
            actorGroups += [group];
        }
    }

    ready = TRUE;
    llOwnerSay("RIVER LINKS READY: actor prim=" + (string)llGetListLength(actorLinks) + ".");
    return TRUE;
}

captureHome()
{
    moving = FALSE;
    statusTimer = FALSE;
    queuedBoatTravel = FALSE;
    llSetTimerEvent(0.0);
    if (!discover()) return;

    homePositions = [];
    homeRotations = [];
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        integer link = llList2Integer(actorLinks, i);
        vector p = localPos(link);
        rotation r = localRot(link);
        homePositions += [p];
        homeRotations += [r];
        llSetLinkPrimitiveParamsFast(
            link,
            [PRIM_DESC, "HOME|" + STATE_VERSION + "|" + (string)p + "|" + (string)r]
        );
    }

    onboard = [];
    vector boatPos = localPos(llList2Integer(anchorLinks, 4));
    if (llVecDist(boatPos, localPos(boatLeftMarker)) <= llVecDist(boatPos, localPos(boatRightMarker)))
    {
        currentSide = "LEFT";
        boatFacing = "RIGHT";
    }
    else
    {
        currentSide = "RIGHT";
        boatFacing = "LEFT";
    }

    ready = TRUE;
    llOwnerSay("RIVER ACTOR CALIBRATED: " + (string)llGetListLength(actorLinks) + " prim.");
}

integer loadHome()
{
    if (!discover()) return FALSE;

    list positions = [];
    list rotations = [];
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        integer link = llList2Integer(actorLinks, i);
        string desc = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
        list fields = llParseStringKeepNulls(desc, ["|"], []);
        if (
            llGetListLength(fields) < 4
            || upper(llList2String(fields, 0)) != "HOME"
            || upper(llList2String(fields, 1)) != STATE_VERSION
        )
        {
            return FALSE;
        }
        positions += [(vector)llList2String(fields, 2)];
        rotations += [(rotation)llList2String(fields, 3)];
    }

    homePositions = positions;
    homeRotations = rotations;
    ready = TRUE;
    return TRUE;
}

restoreAll()
{
    moving = FALSE;
    statusTimer = FALSE;
    queuedBoatTravel = FALSE;
    llSetTimerEvent(0.0);
    llSetText("", ZERO_VECTOR, 0.0);
    if (!loadHome()) return;

    list rules = [];
    integer batch = 0;
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        rules += [
            PRIM_LINK_TARGET, llList2Integer(actorLinks, i),
            PRIM_POS_LOCAL, llList2Vector(homePositions, i),
            PRIM_ROT_LOCAL, llList2Rot(homeRotations, i)
        ];
        batch++;
        if (batch >= BATCH_SIZE)
        {
            llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
            rules = [];
            batch = 0;
        }
    }
    if (llGetListLength(rules)) llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);

    onboard = [];
    vector boatPos = localPos(llList2Integer(anchorLinks, 4));
    if (llVecDist(boatPos, localPos(boatLeftMarker)) <= llVecDist(boatPos, localPos(boatRightMarker)))
    {
        currentSide = "LEFT";
        boatFacing = "RIGHT";
    }
    else
    {
        currentSide = "RIGHT";
        boatFacing = "LEFT";
    }
}

clearMove()
{
    moveLinks = [];
    moveStartPositions = [];
    moveStartRotations = [];
    moveTargetPositions = [];
    moveTargetRotations = [];
}

addGroupMove(integer group, vector targetAnchor)
{
    integer anchor = llList2Integer(anchorLinks, group);
    vector currentAnchor = localPos(anchor);
    vector delta = targetAnchor - currentAnchor;
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        if (llList2Integer(actorGroups, i) == group)
        {
            integer link = llList2Integer(actorLinks, i);
            vector p = localPos(link);
            rotation r = localRot(link);
            moveLinks += [link];
            moveStartPositions += [p];
            moveStartRotations += [r];
            moveTargetPositions += [p + delta];
            moveTargetRotations += [r];
        }
    }
}

addGroupTurn(integer group, vector pivot, rotation turnRotation)
{
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        if (llList2Integer(actorGroups, i) == group)
        {
            integer link = llList2Integer(actorLinks, i);
            vector p = localPos(link);
            rotation r = localRot(link);
            vector targetPosition = pivot + ((p - pivot) * turnRotation);
            rotation targetRotation = r * turnRotation;

            moveLinks += [link];
            moveStartPositions += [p];
            moveStartRotations += [r];
            moveTargetPositions += [targetPosition];
            moveTargetRotations += [targetRotation];
        }
    }
}

startMovement(float durationValue, string requestedAction)
{
    moveElapsed = 0.0;
    moveDuration = durationValue;
    if (moveDuration < 0.30) moveDuration = 0.30;
    actionName = requestedAction;
    moving = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

list parseActors(string value)
{
    list raw = llParseString2List(upper(value), ["+"], []);
    list result = [];
    integer i;
    for (i = 0; i < llGetListLength(raw); i++)
    {
        string actor = upper(llList2String(raw, i));
        if (groupIndex(actor) >= 0 && actor != "BOAT") result += [actor];
    }
    return result;
}

vector sideMarkerPosition(integer group)
{
    if (currentSide == "LEFT") return localPos(llList2Integer(leftMarkers, group));
    return localPos(llList2Integer(rightMarkers, group));
}

integer actorSide(integer group)
{
    vector p = localPos(llList2Integer(anchorLinks, group));
    vector leftPos = localPos(llList2Integer(leftMarkers, group));
    vector rightPos = localPos(llList2Integer(rightMarkers, group));
    if (llVecDist(p, leftPos) <= llVecDist(p, rightPos)) return 0;
    return 1;
}

string detectInvalidVictim(string value)
{
    string request = upper(value);
    if (llSubStringIndex(request, "DOMBA") >= 0) return "DOMBA";
    if (llSubStringIndex(request, "RUMPUT") >= 0) return "RUMPUT";

    integer shepherdOnBoat = llListFindList(onboard, ["GEMBALA"]) >= 0;
    integer wolfOnBoat = llListFindList(onboard, ["SERIGALA"]) >= 0;
    integer sheepOnBoat = llListFindList(onboard, ["DOMBA"]) >= 0;
    integer grassOnBoat = llListFindList(onboard, ["RUMPUT"]) >= 0;

    if (!shepherdOnBoat && wolfOnBoat && sheepOnBoat) return "DOMBA";
    if (!shepherdOnBoat && sheepOnBoat && grassOnBoat) return "RUMPUT";

    integer sideGembala = actorSide(0);
    integer sideSerigala = actorSide(1);
    integer sideDomba = actorSide(2);
    integer sideRumput = actorSide(3);

    if (sideSerigala == sideDomba && sideGembala != sideDomba) return "DOMBA";
    if (sideDomba == sideRumput && sideGembala != sideDomba) return "RUMPUT";

    return "";
}

startBoatTravel(string targetSide, vector targetBoat)
{
    clearMove();
    vector currentBoat = localPos(llList2Integer(anchorLinks, 4));
    vector delta = targetBoat - currentBoat;

    addGroupMove(4, targetBoat);

    integer i;
    for (i = 0; i < llGetListLength(onboard); i++)
    {
        integer group = groupIndex(llList2String(onboard, i));
        integer anchor = llList2Integer(anchorLinks, group);
        addGroupMove(group, localPos(anchor) + delta);
    }

    pendingSide = targetSide;
    float durationValue = llVecDist(currentBoat, targetBoat) / BOAT_MOVE_SPEED;
    if (durationValue < BOAT_MIN_DURATION) durationValue = BOAT_MIN_DURATION;
    if (durationValue > BOAT_MAX_DURATION) durationValue = BOAT_MAX_DURATION;
    startMovement(durationValue, "BOAT_TRAVEL");
}

finishAction()
{
    moving = FALSE;
    llSetTimerEvent(0.0);

    if (actionName == "BOAT_TURN" && queuedBoatTravel)
    {
        boatFacing = queuedBoatSide;
        queuedBoatTravel = FALSE;
        startBoatTravel(queuedBoatSide, queuedBoatTarget);
        return;
    }

    integer i;
    for (i = 0; i < llGetListLength(pendingAdd); i++)
    {
        string actor = llList2String(pendingAdd, i);
        if (llListFindList(onboard, [actor]) < 0) onboard += [actor];
    }
    for (i = 0; i < llGetListLength(pendingRemove); i++)
    {
        string actor2 = llList2String(pendingRemove, i);
        integer index = llListFindList(onboard, [actor2]);
        if (index >= 0) onboard = llDeleteSubList(onboard, index, index);
    }
    if (pendingSide != "") currentSide = pendingSide;

    string completedAction = actionName;
    if (completedAction == "BOAT_TRAVEL") completedAction = "BOAT";

    pendingAdd = [];
    pendingRemove = [];
    pendingSide = "";
    llMessageLinked(LINK_SET, MSG_ACTION_DONE, completedAction, NULL_KEY);
}

handleAction(string step)
{
    if (!loadHome())
    {
        llOwnerSay("RIVER ACTION DITOLAK: HOME actor belum lengkap.");
        llMessageLinked(LINK_SET, MSG_ACTION_DONE, "ERROR", NULL_KEY);
        return;
    }

    list kv = llParseStringKeepNulls(step, ["="], []);
    string keyValue = upper(llList2String(kv, 0));
    string value = "";
    if (llGetListLength(kv) >= 2)
    {
        value = llDumpList2String(llList2List(kv, 1, -1), "=");
    }

    clearMove();
    pendingAdd = [];
    pendingRemove = [];
    pendingSide = "";
    queuedBoatTravel = FALSE;

    if (keyValue == "LOAD")
    {
        list actors = parseActors(value);
        vector boatPos = localPos(llList2Integer(anchorLinks, 4));
        integer count = llGetListLength(actors);
        integer i;
        for (i = 0; i < count; i++)
        {
            string actor = llList2String(actors, i);
            integer group = groupIndex(actor);
            vector offset = <0.0, 0.0, 0.38>;
            if (count == 2)
            {
                if (i == 0) offset = <0.0, 0.30, 0.38>;
                else offset = <0.0, -0.30, 0.38>;
            }
            addGroupMove(group, boatPos + offset);
            pendingAdd += [actor];
        }
        startMovement(LOAD_DURATION, "LOAD");
    }
    else if (keyValue == "UNLOAD")
    {
        list actors2 = parseActors(value);
        integer j;
        for (j = 0; j < llGetListLength(actors2); j++)
        {
            string actor2 = llList2String(actors2, j);
            integer group2 = groupIndex(actor2);
            addGroupMove(group2, sideMarkerPosition(group2));
            pendingRemove += [actor2];
        }
        startMovement(LOAD_DURATION, "UNLOAD");
    }
    else if (keyValue == "BOAT")
    {
        string targetSide = upper(value);
        integer marker = boatRightMarker;
        if (targetSide == "LEFT") marker = boatLeftMarker;
        vector targetBoat = localPos(marker);

        if (targetSide == currentSide)
        {
            llMessageLinked(LINK_SET, MSG_ACTION_DONE, "BOAT", NULL_KEY);
            return;
        }

        if (boatFacing != targetSide)
        {
            vector pivot = localPos(llList2Integer(anchorLinks, 4));
            rotation turnRotation = llEuler2Rot(<0.0, 0.0, PI>);
            addGroupTurn(4, pivot, turnRotation);

            integer k;
            for (k = 0; k < llGetListLength(onboard); k++)
            {
                integer group3 = groupIndex(llList2String(onboard, k));
                addGroupTurn(group3, pivot, turnRotation);
            }

            queuedBoatTravel = TRUE;
            queuedBoatSide = targetSide;
            queuedBoatTarget = targetBoat;
            startMovement(BOAT_TURN_DURATION, "BOAT_TURN");
        }
        else
        {
            startBoatTravel(targetSide, targetBoat);
        }
    }
    else if (keyValue == "INVALID")
    {
        string victim = detectInvalidVictim(value);
        if (victim == "")
        {
            llSetText("INVALID: " + value, <1.0, 0.05, 0.05>, 1.0);
            actionName = "INVALID";
            statusTimer = TRUE;
            llSetTimerEvent(0.90);
            return;
        }

        integer victimGroup = groupIndex(victim);
        integer victimAnchor = llList2Integer(anchorLinks, victimGroup);
        vector offstage = localPos(victimAnchor) + <0.0, 0.0, -25.0>;
        addGroupMove(victimGroup, offstage);
        pendingRemove = [victim];

        if (victim == "DOMBA")
        {
            llSetText("INVALID: SERIGALA MEMAKAN DOMBA", <1.0, 0.05, 0.05>, 1.0);
        }
        else
        {
            llSetText("INVALID: DOMBA MEMAKAN RUMPUT", <1.0, 0.05, 0.05>, 1.0);
        }

        startMovement(INVALID_DURATION, "INVALID");
    }
    else if (keyValue == "SUCCESS")
    {
        llSetText("SUCCESS", <0.05, 1.0, 0.15>, 1.0);
        actionName = "SUCCESS";
        statusTimer = TRUE;
        llSetTimerEvent(0.90);
    }
    else
    {
        llMessageLinked(LINK_SET, MSG_ACTION_DONE, "ERROR", NULL_KEY);
    }
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        string modeValue = rootMode();
        if (modeValue == "RECOVERY")
        {
            discover();
            llOwnerSay("RIVER ACTOR RECOVERY: posisi tidak diubah dan HOME belum disimpan.");
        }
        else if (modeValue == "EDIT")
        {
            captureHome();
            llOwnerSay("RIVER ACTOR AUTO-CALIBRATE: Reset Scripts saat EDIT.");
        }
        else
        {
            restoreAll();
        }
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_CALIBRATE)
        {
            captureHome();
        }
        else if (number == MSG_EDIT)
        {
            if (rootMode() != "RECOVERY") restoreAll();
            else discover();
        }
        else if (number == MSG_SHOW || number == MSG_RESET || number == MSG_HIDE)
        {
            restoreAll();
        }
        else if (number == MSG_ACTION)
        {
            handleAction(message);
        }
    }

    timer()
    {
        if (statusTimer)
        {
            statusTimer = FALSE;
            llSetTimerEvent(0.0);
            llMessageLinked(LINK_SET, MSG_ACTION_DONE, actionName, NULL_KEY);
            return;
        }

        if (!moving) return;

        moveElapsed += TIMER_STEP;
        float progress = moveElapsed / moveDuration;
        if (progress > 1.0) progress = 1.0;
        float eased = progress * progress * (3.0 - (2.0 * progress));

        list rules = [];
        integer batch = 0;
        integer i;
        for (i = 0; i < llGetListLength(moveLinks); i++)
        {
            vector start = llList2Vector(moveStartPositions, i);
            vector target = llList2Vector(moveTargetPositions, i);
            rotation startRot = llList2Rot(moveStartRotations, i);
            rotation targetRot = llList2Rot(moveTargetRotations, i);
            vector position = start + ((target - start) * eased);
            rotation rot = rotationLerp(startRot, targetRot, eased);

            rules += [
                PRIM_LINK_TARGET, llList2Integer(moveLinks, i),
                PRIM_POS_LOCAL, position,
                PRIM_ROT_LOCAL, rot
            ];
            batch++;
            if (batch >= BATCH_SIZE)
            {
                llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
                rules = [];
                batch = 0;
            }
        }
        if (llGetListLength(rules)) llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);

        if (progress >= 1.0) finishAction();
    }

    changed(integer change)
    {
        if (change & CHANGED_LINK) discover();
        if (change & CHANGED_OWNER) llResetScript();
    }
}
