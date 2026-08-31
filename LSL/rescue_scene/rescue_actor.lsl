// Rescue actor: execute validated movement commands from the scene controller.
integer ACTOR_CHANNEL = -451235;
integer LINK_CONTROLLER_TO_ACTOR = 451235;
integer LINK_ACTOR_TO_CONTROLLER = 451236;

integer TRANSPORT_LINK = 1;
integer TRANSPORT_REGION = 2;

string STATE_VERSION = "RESCUE_V5";
key replyController = NULL_KEY;
string replyRunId = "";
integer replyActionIndex = -1;
integer replyTransport = 0;
float TIMER_STEP = 0.04;
float MOVE_SPEED = 3.8;
float JUMP_HEIGHT = 0.12;
integer BATCH_SIZE = 8;

list robotLinks = [];
list robotHomePositions = [];
list robotHomeRotations = [];
integer robotAnchorLink = 0;
integer robotAnchorIndex = -1;

list beaconLinks = [];
list beaconHomePositions = [];
list beaconHomeRotations = [];
integer beaconAnchorLink = 0;
integer beaconAnchorIndex = -1;

integer originLink = 0;
integer rightLink = 0;
integer downLink = 0;
vector originPosition = ZERO_VECTOR;
vector rightStep = ZERO_VECTOR;
vector downStep = ZERO_VECTOR;

integer ready = FALSE;
integer currentRow = 0;
integer currentCol = 0;

list moveStartPositions = [];
list moveStartRotations = [];
list moveTargetPositions = [];
list hitBackPositions = [];
float moveElapsed = 0.0;
float moveDuration = 0.35;
integer moving = FALSE;
integer updateCellAfterMove = FALSE;
integer targetRow = 0;
integer targetCol = 0;
string moveKind = "";
string actionKeyValue = "";
integer statusTimer = FALSE;

string trim(string value) { return llStringTrim(value, STRING_TRIM); }
string lower(string value) { return llToLower(trim(value)); }
string upper(string value) { return llToUpper(trim(value)); }
integer startsWith(string value, string prefix) { return llSubStringIndex(value, prefix) == 0; }
integer isOwnerSpeaker(key speaker) { return llGetOwnerKey(speaker) == llGetOwner(); }

integer robotName(string name)
{
    name = lower(name);
    if (name == "rescue_robot") return TRUE;
    if (startsWith(name, "rescue_robot#")) return TRUE;
    if (startsWith(name, "rescue_robot__#")) return TRUE;
    return FALSE;
}

integer beaconName(string name)
{
    name = lower(name);
    if (name == "target_beacon") return TRUE;
    if (startsWith(name, "target_beacon#")) return TRUE;
    if (startsWith(name, "target_beacon__#")) return TRUE;
    return FALSE;
}

integer findExact(string target)
{
    target = lower(target);
    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
        if (lower(llGetLinkName(link)) == target) return link;
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

integer discover()
{
    robotLinks = [];
    beaconLinks = [];
    robotAnchorLink = 0;
    robotAnchorIndex = -1;
    beaconAnchorLink = 0;
    beaconAnchorIndex = -1;

    originLink = findExact("grid_origin");
    rightLink = findExact("grid_right");
    downLink = findExact("grid_down");
    if (!originLink || !rightLink || !downLink)
    {
        llOwnerSay("RESCUE ACTOR V5 ERROR: helper grid tidak lengkap.");
        ready = FALSE;
        return FALSE;
    }

    originPosition = localPos(originLink);
    rightStep = localPos(rightLink) - originPosition;
    downStep = localPos(downLink) - originPosition;

    integer count = llGetNumberOfPrims();
    integer link;
    float robotBest = 999999.0;
    float beaconBest = 999999.0;
    integer exactBeacon = findExact("target_beacon");

    for (link = 1; link <= count; link++)
    {
        string name = llGetLinkName(link);
        if (robotName(name))
        {
            integer robotIndex = llGetListLength(robotLinks);
            robotLinks += [link];
            float robotDistance = llVecDist(localPos(link), originPosition);
            if (!robotAnchorLink || robotDistance < robotBest)
            {
                robotAnchorLink = link;
                robotAnchorIndex = robotIndex;
                robotBest = robotDistance;
            }
        }
        if (beaconName(name))
        {
            integer beaconIndex = llGetListLength(beaconLinks);
            beaconLinks += [link];
            float beaconDistance = llVecDist(localPos(link), originPosition + (rightStep * 4.0) + (downStep * 4.0));
            if (link == exactBeacon || (!beaconAnchorLink && beaconDistance < beaconBest))
            {
                beaconAnchorLink = link;
                beaconAnchorIndex = beaconIndex;
                beaconBest = beaconDistance;
            }
            else if (exactBeacon == 0 && beaconDistance < beaconBest)
            {
                beaconAnchorLink = link;
                beaconAnchorIndex = beaconIndex;
                beaconBest = beaconDistance;
            }
        }
    }

    if (llGetListLength(robotLinks) < 1 || !robotAnchorLink)
    {
        llOwnerSay("RESCUE ACTOR V5 ERROR: grup rescue_robot tidak ditemukan.");
        ready = FALSE;
        return FALSE;
    }
    if (llGetListLength(beaconLinks) < 1 || !beaconAnchorLink)
    {
        llOwnerSay("RESCUE ACTOR V5 ERROR: grup target_beacon tidak ditemukan.");
        ready = FALSE;
        return FALSE;
    }

    ready = TRUE;
    return TRUE;
}

string homeDescription(string kind, vector position, rotation rotationValue)
{
    return kind + "|" + STATE_VERSION + "|" + (string)position + "|" + (string)rotationValue;
}

integer parseHome(string description, string expectedKind, vector fallbackPosition, rotation fallbackRotation)
{
    list fields = llParseStringKeepNulls(description, ["|"], []);
    if (llGetListLength(fields) < 4) return FALSE;

    string kind = upper(llList2String(fields, 0));
    string version = upper(llList2String(fields, 1));
    if (kind == "HOME" && version == "RESCUE_V1" && expectedKind == "RESCUE_ROBOT_HOME") return TRUE;
    if (kind != expectedKind || version != STATE_VERSION) return FALSE;
    return TRUE;
}

stopActor()
{
    moving = FALSE;
    statusTimer = FALSE;
    moveKind = "";
    actionKeyValue = "";
    llSetTimerEvent(0.0);
}

captureHomes()
{
    stopActor();
    if (!discover()) return;

    robotHomePositions = [];
    robotHomeRotations = [];
    beaconHomePositions = [];
    beaconHomeRotations = [];

    integer i;
    for (i = 0; i < llGetListLength(robotLinks); i++)
    {
        integer link = llList2Integer(robotLinks, i);
        vector position = localPos(link);
        rotation rotationValue = localRot(link);
        robotHomePositions += [position];
        robotHomeRotations += [rotationValue];
        llSetLinkPrimitiveParamsFast(link, [PRIM_DESC, homeDescription("RESCUE_ROBOT_HOME", position, rotationValue)]);
    }

    for (i = 0; i < llGetListLength(beaconLinks); i++)
    {
        integer beaconLink = llList2Integer(beaconLinks, i);
        vector beaconPosition = localPos(beaconLink);
        rotation beaconRotation = localRot(beaconLink);
        beaconHomePositions += [beaconPosition];
        beaconHomeRotations += [beaconRotation];
        llSetLinkPrimitiveParamsFast(beaconLink, [PRIM_DESC, homeDescription("RESCUE_BEACON_HOME", beaconPosition, beaconRotation)]);
    }

    currentRow = 0;
    currentCol = 0;
    ready = TRUE;
    llOwnerSay("RESCUE ACTOR V5 CALIBRATED: robot=" + (string)llGetListLength(robotLinks) + ", beacon=" + (string)llGetListLength(beaconLinks) + ".");
}

integer loadHomes()
{
    if (!discover()) return FALSE;

    list robotPositions = [];
    list robotRotations = [];
    list beaconPositions = [];
    list beaconRotations = [];
    integer i;

    for (i = 0; i < llGetListLength(robotLinks); i++)
    {
        integer link = llList2Integer(robotLinks, i);
        string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
        list fields = llParseStringKeepNulls(description, ["|"], []);
        if (llGetListLength(fields) < 4) return FALSE;
        string kind = upper(llList2String(fields, 0));
        string version = upper(llList2String(fields, 1));
        if (!((kind == "RESCUE_ROBOT_HOME" && (version == STATE_VERSION || version == "RESCUE_V4" || version == "RESCUE_V3")) || (kind == "HOME" && version == "RESCUE_V1"))) return FALSE;
        robotPositions += [(vector)llList2String(fields, 2)];
        robotRotations += [(rotation)llList2String(fields, 3)];
    }

    for (i = 0; i < llGetListLength(beaconLinks); i++)
    {
        integer beaconLink = llList2Integer(beaconLinks, i);
        string beaconDescription = llList2String(llGetLinkPrimitiveParams(beaconLink, [PRIM_DESC]), 0);
        list beaconFields = llParseStringKeepNulls(beaconDescription, ["|"], []);
        if (llGetListLength(beaconFields) < 4) return FALSE;
        if (upper(llList2String(beaconFields, 0)) != "RESCUE_BEACON_HOME") return FALSE;
        string beaconVersion = upper(llList2String(beaconFields, 1));
        if (beaconVersion != STATE_VERSION && beaconVersion != "RESCUE_V4" && beaconVersion != "RESCUE_V3") return FALSE;
        beaconPositions += [(vector)llList2String(beaconFields, 2)];
        beaconRotations += [(rotation)llList2String(beaconFields, 3)];
    }

    robotHomePositions = robotPositions;
    robotHomeRotations = robotRotations;
    beaconHomePositions = beaconPositions;
    beaconHomeRotations = beaconRotations;
    ready = TRUE;
    return TRUE;
}

applyGroup(list links, list positions, list rotations)
{
    list rules = [];
    integer batch = 0;
    integer i;
    for (i = 0; i < llGetListLength(links); i++)
    {
        rules += [
            PRIM_LINK_TARGET, llList2Integer(links, i),
            PRIM_POS_LOCAL, llList2Vector(positions, i),
            PRIM_ROT_LOCAL, llList2Rot(rotations, i)
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
}

beaconInactive()
{
    integer i;
    for (i = 0; i < llGetListLength(beaconLinks); i++)
    {
        integer link = llList2Integer(beaconLinks, i);
        llSetLinkAlpha(link, 1.0, ALL_SIDES);
        llSetLinkPrimitiveParamsFast(link, [
            PRIM_FULLBRIGHT, ALL_SIDES, FALSE,
            PRIM_GLOW, ALL_SIDES, 0.0
        ]);
    }
}

beaconGoal(integer row, integer col)
{
    vector desiredAnchor = originPosition + (downStep * (float)row) + (rightStep * (float)col);
    vector homeAnchor = llList2Vector(beaconHomePositions, beaconAnchorIndex);
    vector delta = desiredAnchor - homeAnchor;
    list positions = [];
    integer i;
    for (i = 0; i < llGetListLength(beaconHomePositions); i++)
        positions += [llList2Vector(beaconHomePositions, i) + delta];
    applyGroup(beaconLinks, positions, beaconHomeRotations);

    for (i = 0; i < llGetListLength(beaconLinks); i++)
    {
        integer link = llList2Integer(beaconLinks, i);
        llSetLinkAlpha(link, 1.0, ALL_SIDES);
        llSetLinkPrimitiveParamsFast(link, [
            PRIM_FULLBRIGHT, ALL_SIDES, TRUE,
            PRIM_GLOW, ALL_SIDES, 0.35
        ]);
    }
}

restoreAll()
{
    stopActor();
    llSetText("", ZERO_VECTOR, 0.0);
    if (!loadHomes())
    {
        captureHomes();
        if (!loadHomes()) return;
    }
    applyGroup(robotLinks, robotHomePositions, robotHomeRotations);
    applyGroup(beaconLinks, beaconHomePositions, beaconHomeRotations);
    currentRow = 0;
    currentCol = 0;
    beaconInactive();
}

vector cellPosition(integer row, integer col)
{
    return originPosition + (downStep * (float)row) + (rightStep * (float)col);
}

integer coordinateValid(string value)
{
    list parts = llParseStringKeepNulls(value, [","], []);
    if (llGetListLength(parts) != 2) return FALSE;
    string rowText = trim(llList2String(parts, 0));
    string colText = trim(llList2String(parts, 1));
    if (rowText == "" || colText == "") return FALSE;
    integer row = (integer)rowText;
    integer col = (integer)colText;
    if ((string)row != rowText || (string)col != colText) return FALSE;
    return row >= 0 && row <= 4 && col >= 0 && col <= 4;
}

list parseCoordinate(string value)
{
    list parts = llParseStringKeepNulls(value, [","], []);
    return [(integer)llList2String(parts, 0), (integer)llList2String(parts, 1)];
}

sendTransportReply(integer transport, key controller, string message)
{
    if (transport == TRANSPORT_LINK)
    {
        llMessageLinked(LINK_SET, LINK_ACTOR_TO_CONTROLLER, message, llGetKey());
        return;
    }

    if (controller != NULL_KEY)
        llRegionSayTo(controller, ACTOR_CHANNEL, message);
}

sendActorReply(string resultType, string detail)
{
    if (replyController == NULL_KEY) return;
    sendTransportReply(
        replyTransport,
        replyController,
        "DONE|" + replyRunId
        + "|" + (string)replyActionIndex
        + "|" + resultType
        + "|" + detail
    );
}

clearReply()
{
    replyController = NULL_KEY;
    replyRunId = "";
    replyActionIndex = -1;
    replyTransport = 0;
}

sendDone(string keyValue)
{
    sendActorReply("OK", keyValue);
    clearReply();
}

sendError(string detail)
{
    stopActor();
    sendActorReply("ERROR", detail);
    clearReply();
}

sendReady(integer transport, key controller, string token)
{
    integer homeReady = FALSE;
    if (ready && llGetListLength(robotHomePositions) == llGetListLength(robotLinks)
        && llGetListLength(beaconHomePositions) == llGetListLength(beaconLinks))
        homeReady = TRUE;

    string resultType = "ERROR";
    if (ready && llGetListLength(robotLinks) > 0 && llGetListLength(beaconLinks) > 0 && homeReady)
        resultType = "OK";

    sendTransportReply(
        transport,
        controller,
        "READY|" + token
        + "|" + resultType
        + "|" + (string)llGetListLength(robotLinks)
        + "|" + (string)llGetListLength(beaconLinks)
        + "|" + (string)homeReady
    );
}

handleControl(integer transport, key controller, string token, string command)
{
    command = upper(command);
    if (command == "CALIBRATE") captureHomes();
    else restoreAll();

    string resultType = "ERROR";
    if (ready) resultType = "OK";
    sendTransportReply(transport, controller, "CTL_DONE|" + token + "|" + resultType + "|" + command);
}

handleActorMessage(integer transport, key speaker, string message)
{
    if (!isOwnerSpeaker(speaker)) return;

    list fields = llParseStringKeepNulls(message, ["|"], []);
    string command = upper(llList2String(fields, 0));

    if (command == "PING")
    {
        if (llGetListLength(fields) < 2) return;
        if (!loadHomes())
        {
            captureHomes();
            loadHomes();
        }
        beaconInactive();
        sendReady(transport, speaker, llList2String(fields, 1));
        return;
    }

    if (command == "CTL")
    {
        if (llGetListLength(fields) < 3) return;
        handleControl(transport, speaker, llList2String(fields, 1), llList2String(fields, 2));
        return;
    }

    if (command == "ACT")
    {
        if (llGetListLength(fields) < 4) return;
        if (moving || statusTimer)
        {
            replyController = speaker;
            replyTransport = transport;
            replyRunId = llList2String(fields, 1);
            replyActionIndex = (integer)llList2String(fields, 2);
            sendError("ACTOR_SEDANG_SIBUK");
            return;
        }

        replyController = speaker;
        replyTransport = transport;
        replyRunId = llList2String(fields, 1);
        replyActionIndex = (integer)llList2String(fields, 2);
        handleAction(llDumpList2String(llList2List(fields, 3, -1), "|"));
    }
}

positionRobotAt(integer row, integer col)
{
    vector desiredAnchor = cellPosition(row, col);
    vector homeAnchor = llList2Vector(robotHomePositions, robotAnchorIndex);
    vector delta = desiredAnchor - homeAnchor;
    list positions = [];
    integer i;
    for (i = 0; i < llGetListLength(robotHomePositions); i++)
        positions += [llList2Vector(robotHomePositions, i) + delta];
    applyGroup(robotLinks, positions, robotHomeRotations);
    currentRow = row;
    currentCol = col;
}

beginRobotMove(list targetPositions, float duration, string kind, integer row, integer col, integer updateCell)
{
    moveStartPositions = [];
    moveStartRotations = [];
    moveTargetPositions = targetPositions;
    integer i;
    for (i = 0; i < llGetListLength(robotLinks); i++)
    {
        integer link = llList2Integer(robotLinks, i);
        moveStartPositions += [localPos(link)];
        moveStartRotations += [localRot(link)];
    }
    moveElapsed = 0.0;
    moveDuration = duration;
    if (moveDuration < 0.20) moveDuration = 0.20;
    moveKind = kind;
    targetRow = row;
    targetCol = col;
    updateCellAfterMove = updateCell;
    moving = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

moveRobotToCell(integer row, integer col)
{
    vector currentAnchor = localPos(robotAnchorLink);
    vector targetAnchor = cellPosition(row, col);
    vector delta = targetAnchor - currentAnchor;
    list targets = [];
    integer i;
    for (i = 0; i < llGetListLength(robotLinks); i++)
        targets += [localPos(llList2Integer(robotLinks, i)) + delta];
    float duration = llVecDist(currentAnchor, targetAnchor) / MOVE_SPEED;
    beginRobotMove(targets, duration, "MOVE", row, col, TRUE);
}

beginStatus(string text, vector color, string keyValue)
{
    llSetText(text, color, 1.0);
    actionKeyValue = keyValue;
    statusTimer = TRUE;
    llSetTimerEvent(0.75);
}

finishMovement()
{
    moving = FALSE;
    llSetTimerEvent(0.0);
    if (updateCellAfterMove)
    {
        currentRow = targetRow;
        currentCol = targetCol;
    }

    if (moveKind == "HIT_OUT")
    {
        beginRobotMove(hitBackPositions, 0.25, "HIT_BACK", currentRow, currentCol, FALSE);
        return;
    }
    if (moveKind == "HIT_BACK")
    {
        beginStatus("MENABRAK DINDING", <0.85, 0.08, 0.05>, "HIT_WALL");
        return;
    }
    if (moveKind == "BOUNDARY_OUT")
    {
        beginRobotMove(hitBackPositions, 0.25, "BOUNDARY_BACK", currentRow, currentCol, FALSE);
        return;
    }
    if (moveKind == "BOUNDARY_BACK")
    {
        beginStatus("KELUAR PAPAN", <0.85, 0.15, 0.05>, "OUT_OF_GRID");
        return;
    }
    sendDone(actionKeyValue);
}

handleAction(string step)
{
    if (!loadHomes())
    {
        sendError("HOME_BELUM_VALID");
        return;
    }

    list fields = llParseStringKeepNulls(step, ["="], []);
    string keyValue = upper(llList2String(fields, 0));
    string value = "";
    if (llGetListLength(fields) > 1)
        value = trim(llDumpList2String(llList2List(fields, 1, -1), "="));
    actionKeyValue = keyValue;

    if (keyValue == "START")
    {
        if (!coordinateValid(value)) { sendError("START_TIDAK_VALID"); return; }
        restoreAll();
        list rc = parseCoordinate(value);
        positionRobotAt(llList2Integer(rc, 0), llList2Integer(rc, 1));
        sendDone("START");
    }
    else if (keyValue == "MOVE")
    {
        integer row = currentRow;
        integer col = currentCol;
        string direction = upper(value);
        if (direction == "UP") row--;
        else if (direction == "DOWN") row++;
        else if (direction == "LEFT") col--;
        else if (direction == "RIGHT") col++;
        else { sendError("MOVE_TIDAK_VALID"); return; }
        if (row < 0 || row > 4 || col < 0 || col > 4) { sendError("MOVE_KELUAR_PAPAN"); return; }
        moveRobotToCell(row, col);
    }
    else if (keyValue == "HIT_WALL")
    {
        if (!coordinateValid(value)) { sendError("HIT_WALL_TIDAK_VALID"); return; }
        list wall = parseCoordinate(value);
        vector currentAnchor = localPos(robotAnchorLink);
        vector wallPosition = cellPosition(llList2Integer(wall, 0), llList2Integer(wall, 1));
        vector halfwayDelta = (wallPosition - currentAnchor) * 0.45;
        list targets = [];
        hitBackPositions = [];
        integer i;
        for (i = 0; i < llGetListLength(robotLinks); i++)
        {
            vector current = localPos(llList2Integer(robotLinks, i));
            hitBackPositions += [current];
            targets += [current + halfwayDelta];
        }
        beginRobotMove(targets, 0.28, "HIT_OUT", currentRow, currentCol, FALSE);
    }
    else if (keyValue == "OUT_OF_GRID")
    {
        string direction2 = upper(value);
        if (!(direction2 == "UP" || direction2 == "DOWN" || direction2 == "LEFT" || direction2 == "RIGHT"))
        { sendError("OUT_OF_GRID_TIDAK_VALID"); return; }

        integer outsideRow = currentRow;
        integer outsideCol = currentCol;
        if (direction2 == "UP") outsideRow--;
        else if (direction2 == "DOWN") outsideRow++;
        else if (direction2 == "LEFT") outsideCol--;
        else if (direction2 == "RIGHT") outsideCol++;

        vector currentAnchor2 = localPos(robotAnchorLink);
        vector outsidePosition = cellPosition(outsideRow, outsideCol);
        vector boundaryDelta = (outsidePosition - currentAnchor2) * 0.45;
        list boundaryTargets = [];
        hitBackPositions = [];
        integer boundaryIndex;
        for (boundaryIndex = 0; boundaryIndex < llGetListLength(robotLinks); boundaryIndex++)
        {
            vector currentPart = localPos(llList2Integer(robotLinks, boundaryIndex));
            hitBackPositions += [currentPart];
            boundaryTargets += [currentPart + boundaryDelta];
        }
        beginRobotMove(boundaryTargets, 0.28, "BOUNDARY_OUT", currentRow, currentCol, FALSE);
    }
    else if (keyValue == "INVALID_STEP")
    {
        if (value == "") { sendError("INVALID_STEP_KOSONG"); return; }
        beginStatus("LANGKAH TIDAK DAPAT DIJALANKAN", <0.85, 0.15, 0.05>, "INVALID_STEP");
    }
    else if (keyValue == "INCOMPLETE")
    {
        beginStatus("TARGET BELUM TERCAPAI", <0.85, 0.55, 0.05>, "INCOMPLETE");
    }
    else if (keyValue == "GOAL")
    {
        if (!coordinateValid(value)) { sendError("GOAL_TIDAK_VALID"); return; }
        list goal = parseCoordinate(value);
        integer goalRow = llList2Integer(goal, 0);
        integer goalCol = llList2Integer(goal, 1);
        if (currentRow != goalRow || currentCol != goalCol) { sendError("ROBOT_BELUM_DI_GOAL"); return; }
        beaconGoal(goalRow, goalCol);
        beginStatus("TARGET TERCAPAI", <0.05, 0.75, 0.18>, "GOAL");
    }
    else sendError("ACTION_TIDAK_DIDUKUNG");
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        llListen(ACTOR_CHANNEL, "", NULL_KEY, "");
        if (!loadHomes()) captureHomes();
        restoreAll();
        llOwnerSay(
            "RESCUE ACTOR V5 READY: channel=-451235, robot="
            + (string)llGetListLength(robotLinks)
            + ", beacon=" + (string)llGetListLength(beaconLinks)
            + "."
        );
    }

    listen(integer channel, string name, key speaker, string message)
    {
        if (channel != ACTOR_CHANNEL) return;
        // Ignore chat sent by this same object. Same-object controller uses link_message.
        if (speaker == llGetKey()) return;
        handleActorMessage(TRANSPORT_REGION, speaker, message);
    }

    link_message(integer senderNumber, integer number, string message, key id)
    {
        if (number != LINK_CONTROLLER_TO_ACTOR) return;
        handleActorMessage(TRANSPORT_LINK, id, message);
    }

    timer()
    {
        if (statusTimer)
        {
            statusTimer = FALSE;
            llSetTimerEvent(0.0);
            sendDone(actionKeyValue);
            return;
        }
        if (!moving) return;

        moveElapsed += TIMER_STEP;
        float progress = moveElapsed / moveDuration;
        if (progress > 1.0) progress = 1.0;
        float eased = progress * progress * (3.0 - (2.0 * progress));
        float arcOffset = llSin(PI * progress) * JUMP_HEIGHT;

        list rules = [];
        integer batch = 0;
        integer i;
        for (i = 0; i < llGetListLength(robotLinks); i++)
        {
            vector start = llList2Vector(moveStartPositions, i);
            vector target = llList2Vector(moveTargetPositions, i);
            vector position = start + ((target - start) * eased) + <0.0, 0.0, arcOffset>;
            rules += [
                PRIM_LINK_TARGET, llList2Integer(robotLinks, i),
                PRIM_POS_LOCAL, position,
                PRIM_ROT_LOCAL, llList2Rot(moveStartRotations, i)
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
        if (progress >= 1.0) finishMovement();
    }

    changed(integer change)
    {
        if (change & CHANGED_LINK)
        {
            discover();
            loadHomes();
            beaconInactive();
        }
        if (change & CHANGED_OWNER) llResetScript();
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }
}
