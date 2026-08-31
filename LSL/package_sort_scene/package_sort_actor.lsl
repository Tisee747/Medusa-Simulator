// Package-sort actor: react to scene calibration, visibility, and reset events.
integer MSG_EDIT = 9601;
integer MSG_CALIBRATE = 9602;
integer MSG_SHOW = 9603;
integer MSG_RESET = 9604;
integer MSG_HIDE = 9605;
integer MSG_ACTION = 9610;
integer MSG_ACTION_DONE = 9611;
integer MSG_ACTION_FAILED = 9612;

string STATE_VERSION = "PACKAGE_V2";
float TIMER_STEP = 0.04;
float LIFT_HEIGHT = 0.90;
float MOVE_SPEED = 5.5;
float GENERIC_CHILD_MAX_DISTANCE = 1.25;
integer BATCH_SIZE = 8;

list actorLinks = [];
list actorGroups = [];
list homePositions = [];
list homeRotations = [];
list anchorLinks = [];
list slotLinks = [];
integer sorterLink = 0;
vector sorterHome = ZERO_VECTOR;
rotation sorterHomeRot = ZERO_ROTATION;
vector sorterHomeEuler = ZERO_VECTOR;
float sorterCenterAngle = 0.0;
float sorterPickAngle = PI_BY_TWO;
float sorterDropAngle = -PI_BY_TWO;
integer ready = FALSE;

list moveLinks = [];
list moveStartPositions = [];
list moveStartRotations = [];
list moveTargetPositions = [];
float moveElapsed = 0.0;
float moveDuration = 0.5;
integer moving = FALSE;
string actionName = "";
integer activeGroup = -1;
integer activeSlot = -1;
integer highlightMode = FALSE;
float sorterAngle = PI_BY_TWO;
float sorterStartAngle = PI_BY_TWO;
float sorterTargetAngle = PI_BY_TWO;


rotation sorterRotation(float angleOffset)
{
    vector eulerValue = sorterHomeEuler;
    eulerValue.z += angleOffset;
    return llEuler2Rot(eulerValue);
}

float smooth01(float value)
{
    if (value <= 0.0) return 0.0;
    if (value >= 1.0) return 1.0;
    return value * value * (3.0 - (2.0 * value));
}

float sorterAngleThroughCenter(float startAngle, float targetAngle, float progress)
{
    if ((startAngle < 0.0 && targetAngle > 0.0) || (startAngle > 0.0 && targetAngle < 0.0))
    {
        if (progress < 0.45)
        {
            float firstProgress = smooth01(progress / 0.45);
            return startAngle + ((sorterCenterAngle - startAngle) * firstProgress);
        }
        if (progress < 0.55)
        {
            return sorterCenterAngle;
        }
        float secondProgress = smooth01((progress - 0.55) / 0.45);
        return sorterCenterAngle + ((targetAngle - sorterCenterAngle) * secondProgress);
    }

    return startAngle + ((targetAngle - startAngle) * smooth01(progress));
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

integer packageIndex(string value)
{
    value = upper(value);
    if (value == "PACKAGE_1") return 0;
    if (value == "PACKAGE_2") return 1;
    if (value == "PACKAGE_3") return 2;
    if (value == "PACKAGE_4") return 3;
    if (value == "PACKAGE_5") return 4;
    return -1;
}

integer slotIndex(string value)
{
    value = upper(value);
    if (value == "SLOT_1") return 0;
    if (value == "SLOT_2") return 1;
    if (value == "SLOT_3") return 2;
    if (value == "SLOT_4") return 3;
    if (value == "SLOT_5") return 4;
    return -1;
}

integer explicitPackageGroup(string name)
{
    integer i;
    for (i = 1; i <= 5; i++)
    {
        string base = "package_" + (string)i;
        if (name == base || startsWith(name, base + "#") || startsWith(name, base + "__#"))
        {
            return i - 1;
        }
    }
    return -1;
}

integer isGenericPackageChild(string name)
{
    if (name == "package#1") return TRUE;
    if (startsWith(name, "package#")) return TRUE;
    if (startsWith(name, "package__#")) return TRUE;
    return FALSE;
}

integer nearestType(vector position, list packagePositions, list slotPositions)
{
    integer bestType = -1;
    float bestDistance = 999999.0;
    integer i;
    for (i = 0; i < 5; i++)
    {
        float packageDistance = llVecDist(position, llList2Vector(packagePositions, i));
        if (packageDistance < bestDistance)
        {
            bestDistance = packageDistance;
            bestType = i;
        }

        float slotDistance = llVecDist(position, llList2Vector(slotPositions, i));
        if (slotDistance < bestDistance)
        {
            bestDistance = slotDistance;
            bestType = 100 + i;
        }
    }
    return bestType;
}

integer prepareFixedLinks()
{
    anchorLinks = [];
    slotLinks = [];

    integer i;
    for (i = 1; i <= 5; i++)
    {
        integer packageLink = findExact("package_" + (string)i);
        integer slotLink = findExact("slot_" + (string)i);
        if (!packageLink || !slotLink)
        {
            llOwnerSay("PACKAGE ERROR: package_" + (string)i + " atau slot_" + (string)i + " tidak ditemukan.");
            return FALSE;
        }
        anchorLinks += [packageLink];
        slotLinks += [slotLink];
    }

    sorterLink = findExact("sorter_head");
    if (!sorterLink)
    {
        llOwnerSay("PACKAGE ERROR: sorter_head tidak ditemukan.");
        return FALSE;
    }
    return TRUE;
}

integer discoverForCalibration()
{
    actorLinks = [];
    actorGroups = [];
    ready = FALSE;

    if (!prepareFixedLinks()) return FALSE;

    list packagePositions = [];
    list slotPositions = [];
    integer i;
    for (i = 0; i < 5; i++)
    {
        packagePositions += [localPos(llList2Integer(anchorLinks, i))];
        slotPositions += [localPos(llList2Integer(slotLinks, i))];
    }

    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
    {
        string name = lower(llGetLinkName(link));
        integer group = explicitPackageGroup(name);
        if (group >= 0)
        {
            actorLinks += [link];
            actorGroups += [group];
        }
    }

    for (link = 1; link <= count; link++)
    {
        string genericName = lower(llGetLinkName(link));
        if (isGenericPackageChild(genericName))
        {
            integer nearest = nearestType(localPos(link), packagePositions, slotPositions);
            if (nearest >= 0 && nearest < 5)
            {
                float distance = llVecDist(localPos(link), llList2Vector(packagePositions, nearest));
                if (distance <= GENERIC_CHILD_MAX_DISTANCE)
                {
                    actorLinks += [link];
                    actorGroups += [nearest];
                }
            }
        }
    }

    for (i = 0; i < 5; i++)
    {
        integer groupCount = 0;
        integer j;
        for (j = 0; j < llGetListLength(actorGroups); j++)
        {
            if (llList2Integer(actorGroups, j) == i) groupCount++;
        }
        if (groupCount < 1)
        {
            llOwnerSay("PACKAGE ERROR: group PACKAGE_" + (string)(i + 1) + " tidak ditemukan.");
            return FALSE;
        }
    }

    llOwnerSay("PACKAGE GROUPING READY: actor prim=" + (string)llGetListLength(actorLinks) + ", sorter_head statis=1.");
    return TRUE;
}

integer loadHome()
{
    actorLinks = [];
    actorGroups = [];
    homePositions = [];
    homeRotations = [];
    ready = FALSE;

    if (!prepareFixedLinks()) return FALSE;

    integer count = llGetNumberOfPrims();
    integer link;
    for (link = 1; link <= count; link++)
    {
        string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
        list fields = llParseStringKeepNulls(description, ["|"], []);
        if (
            llGetListLength(fields) >= 5
            && upper(llList2String(fields, 0)) == "PKG"
            && upper(llList2String(fields, 1)) == STATE_VERSION
        )
        {
            integer group = (integer)llList2String(fields, 2);
            if (group >= 0 && group < 5)
            {
                actorLinks += [link];
                actorGroups += [group];
                homePositions += [(vector)llList2String(fields, 3)];
                homeRotations += [(rotation)llList2String(fields, 4)];
            }
        }
    }

    list missing = [];
    integer i;
    for (i = 0; i < 5; i++)
    {
        integer anchor = llList2Integer(anchorLinks, i);
        if (llListFindList(actorLinks, [anchor]) < 0)
        {
            missing += [(string)anchor + ":package_" + (string)(i + 1)];
        }
    }

    string sorterDescription = llList2String(llGetLinkPrimitiveParams(sorterLink, [PRIM_DESC]), 0);
    list sorterFields = llParseStringKeepNulls(sorterDescription, ["|"], []);
    if (
        llGetListLength(sorterFields) < 4
        || upper(llList2String(sorterFields, 0)) != "HOME"
        || upper(llList2String(sorterFields, 1)) != STATE_VERSION
    )
    {
        missing += [(string)sorterLink + ":sorter_head"];
    }

    if (llGetListLength(missing) > 0 || llGetListLength(actorLinks) < 5)
    {
        llOwnerSay("PACKAGE HOME V2 BELUM LENGKAP. Missing=" + llDumpList2String(missing, ", "));
        return FALSE;
    }

    sorterHome = (vector)llList2String(sorterFields, 2);
    sorterHomeRot = (rotation)llList2String(sorterFields, 3);
    sorterHomeEuler = llRot2Euler(sorterHomeRot);
    sorterCenterAngle = 0.0;
    sorterPickAngle = PI_BY_TWO;
    sorterDropAngle = -PI_BY_TWO;
    ready = TRUE;
    return TRUE;
}

captureHome()
{
    moving = FALSE;
    highlightMode = FALSE;
    llSetTimerEvent(0.0);

    if (!discoverForCalibration()) return;

    homePositions = [];
    homeRotations = [];
    integer count = llGetListLength(actorLinks);
    integer i;
    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(actorLinks, i);
        integer group = llList2Integer(actorGroups, i);
        vector position = localPos(link);
        rotation rot = localRot(link);
        homePositions += [position];
        homeRotations += [rot];
        llSetLinkPrimitiveParamsFast(
            link,
            [PRIM_DESC, "PKG|" + STATE_VERSION + "|" + (string)group + "|" + (string)position + "|" + (string)rot]
        );
    }

    sorterHome = localPos(sorterLink);
    sorterHomeRot = localRot(sorterLink);
    sorterHomeEuler = llRot2Euler(sorterHomeRot);
    sorterCenterAngle = 0.0;
    sorterPickAngle = PI_BY_TWO;
    sorterDropAngle = -PI_BY_TWO;
    llSetLinkPrimitiveParamsFast(
        sorterLink,
        [PRIM_DESC, "HOME|" + STATE_VERSION + "|" + (string)sorterHome + "|" + (string)sorterHomeRot]
    );

    ready = TRUE;
    activeGroup = -1;
    activeSlot = -1;
    sorterAngle = sorterCenterAngle;
    sorterStartAngle = sorterCenterAngle;
    sorterTargetAngle = sorterCenterAngle;
    llSetLinkPrimitiveParamsFast(sorterLink, [PRIM_GLOW, ALL_SIDES, 0.0]);
    llOwnerSay("PACKAGE ACTOR CALIBRATED V8: paket prim=" + (string)count + ", sorter_head HOME=tengah, PICK=+90 derajat, DROP=-90 derajat.");
}

setGlowForGroup(integer group, float glow)
{
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        if (llList2Integer(actorGroups, i) == group)
        {
            llSetLinkPrimitiveParamsFast(llList2Integer(actorLinks, i), [PRIM_GLOW, ALL_SIDES, glow]);
        }
    }
}

restoreAll()
{
    moving = FALSE;
    highlightMode = FALSE;
    llSetTimerEvent(0.0);
    if (!loadHome()) return;

    list rules = [];
    integer batch = 0;
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        integer link = llList2Integer(actorLinks, i);
        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, llList2Vector(homePositions, i),
            PRIM_ROT_LOCAL, llList2Rot(homeRotations, i),
            PRIM_GLOW, ALL_SIDES, 0.0
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

    sorterAngle = sorterCenterAngle;
    sorterStartAngle = sorterCenterAngle;
    sorterTargetAngle = sorterCenterAngle;
    llSetLinkPrimitiveParamsFast(
        sorterLink,
        [PRIM_POS_LOCAL, sorterHome, PRIM_ROT_LOCAL, sorterHomeRot, PRIM_GLOW, ALL_SIDES, 0.0]
    );
    activeGroup = -1;
    activeSlot = -1;
}

prepareMove(integer group, vector targetAnchor, string requestedAction, float requestedSorterAngle)
{
    moveLinks = [];
    moveStartPositions = [];
    moveStartRotations = [];
    moveTargetPositions = [];

    integer anchor = llList2Integer(anchorLinks, group);
    vector currentAnchor = localPos(anchor);
    vector delta = targetAnchor - currentAnchor;
    integer i;
    for (i = 0; i < llGetListLength(actorLinks); i++)
    {
        if (llList2Integer(actorGroups, i) == group)
        {
            integer link = llList2Integer(actorLinks, i);
            vector position = localPos(link);
            moveLinks += [link];
            moveStartPositions += [position];
            moveStartRotations += [localRot(link)];
            moveTargetPositions += [position + delta];
        }
    }

    float distance = llVecDist(currentAnchor, targetAnchor);
    moveDuration = distance / MOVE_SPEED;
    if (requestedAction == "PICK" && moveDuration < 0.90) moveDuration = 0.90;
    else if (requestedAction == "DROP" && moveDuration < 0.55) moveDuration = 0.55;
    else if (moveDuration < 0.55) moveDuration = 0.55;
    moveElapsed = 0.0;
    actionName = requestedAction;
    sorterStartAngle = sorterAngle;
    sorterTargetAngle = requestedSorterAngle;
    moving = TRUE;
    llSetLinkPrimitiveParamsFast(sorterLink, [PRIM_GLOW, ALL_SIDES, 0.0]);
    llSetTimerEvent(TIMER_STEP);
}

finishAction()
{
    moving = FALSE;
    llSetTimerEvent(0.0);
    sorterAngle = sorterTargetAngle;
    llSetLinkPrimitiveParamsFast(
        sorterLink,
        [
            PRIM_POS_LOCAL, sorterHome,
            PRIM_ROT_LOCAL, sorterRotation(sorterAngle),
            PRIM_GLOW, ALL_SIDES, 0.0
        ]
    );
    llMessageLinked(LINK_SET, MSG_ACTION_DONE, actionName, NULL_KEY);
}

handleAction(string message)
{
    if (!loadHome())
    {
        llOwnerSay("PACKAGE ACTION DITOLAK: HOME V2 belum lengkap. Sequence dihentikan.");
        llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "HOME_INCOMPLETE", NULL_KEY);
        return;
    }

    list parts = llParseStringKeepNulls(message, ["|"], []);
    string packageValue = upper(llList2String(parts, 0));
    string actionValue = upper(llList2String(parts, 1));
    string targetValue = upper(llList2String(parts, 2));
    integer group = packageIndex(packageValue);
    if (group < 0)
    {
        llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "INVALID_PACKAGE", NULL_KEY);
        return;
    }

    activeGroup = group;
    integer anchor = llList2Integer(anchorLinks, group);
    vector currentAnchor = localPos(anchor);

    if (actionValue == "PICK")
    {
        prepareMove(group, currentAnchor + <0.0, 0.0, LIFT_HEIGHT>, "PICK", sorterPickAngle);
    }
    else if (actionValue == "MOVE")
    {
        integer targetIndex = slotIndex(targetValue);
        if (targetIndex < 0)
        {
            llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "INVALID_SLOT", NULL_KEY);
            return;
        }
        activeSlot = targetIndex;
        vector slotPosition = localPos(llList2Integer(slotLinks, targetIndex));
        prepareMove(group, slotPosition + <0.0, 0.0, LIFT_HEIGHT>, "MOVE", sorterDropAngle);
    }
    else if (actionValue == "DROP")
    {
        if (activeSlot < 0)
        {
            llOwnerSay("PACKAGE DROP DITOLAK: belum ada TARGET slot.");
            llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "NO_TARGET", NULL_KEY);
            return;
        }
        prepareMove(group, localPos(llList2Integer(slotLinks, activeSlot)), "DROP", sorterDropAngle);
    }
    else if (actionValue == "HIGHLIGHT")
    {
        setGlowForGroup(group, 0.25);
        highlightMode = TRUE;
        actionName = "HIGHLIGHT";
        llSetTimerEvent(0.65);
    }
    else if (actionValue == "RESET" || actionValue == "SHOW")
    {
        integer anchorActorIndex = llListFindList(actorLinks, [anchor]);
        if (anchorActorIndex < 0)
        {
            llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "ANCHOR_HOME_MISSING", NULL_KEY);
            return;
        }
        activeSlot = -1;
        prepareMove(group, llList2Vector(homePositions, anchorActorIndex), actionValue, sorterCenterAngle);
    }
    else
    {
        llMessageLinked(LINK_SET, MSG_ACTION_FAILED, "INVALID_ACTION", NULL_KEY);
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
            discoverForCalibration();
            llOwnerSay("PACKAGE ACTOR RECOVERY V8: posisi tidak diubah. Tekan EDIT lalu CALIBRATE.");
        }
        else if (modeValue == "EDIT")
        {
            captureHome();
            llOwnerSay("PACKAGE ACTOR AUTO-CALIBRATE V8: Reset Scripts saat EDIT.");
        }
        else
        {
            restoreAll();
        }
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_CALIBRATE) captureHome();
        else if (number == MSG_EDIT)
        {
            if (rootMode() != "RECOVERY") restoreAll();
            else discoverForCalibration();
        }
        else if (number == MSG_SHOW || number == MSG_RESET || number == MSG_HIDE) restoreAll();
        else if (number == MSG_ACTION) handleAction(message);
    }

    timer()
    {
        if (highlightMode)
        {
            highlightMode = FALSE;
            llSetTimerEvent(0.0);
            setGlowForGroup(activeGroup, 0.0);
            llMessageLinked(LINK_SET, MSG_ACTION_DONE, "HIGHLIGHT", NULL_KEY);
            return;
        }

        if (!moving) return;

        moveElapsed += TIMER_STEP;
        float progress = moveElapsed / moveDuration;
        if (progress > 1.0) progress = 1.0;
        float objectProgress = smooth01(progress);

        if (actionName == "PICK")
        {
            if (progress < 0.50) objectProgress = 0.0;
            else objectProgress = smooth01((progress - 0.50) / 0.50);
        }

        list rules = [];
        integer batch = 0;
        integer i;
        for (i = 0; i < llGetListLength(moveLinks); i++)
        {
            vector startPosition = llList2Vector(moveStartPositions, i);
            vector targetPosition = llList2Vector(moveTargetPositions, i);
            rules += [
                PRIM_LINK_TARGET, llList2Integer(moveLinks, i),
                PRIM_POS_LOCAL, startPosition + ((targetPosition - startPosition) * objectProgress),
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

        float currentSorterAngle = sorterAngleThroughCenter(sorterStartAngle, sorterTargetAngle, progress);
        llSetLinkPrimitiveParamsFast(
            sorterLink,
            [
                PRIM_POS_LOCAL, sorterHome,
                PRIM_ROT_LOCAL, sorterRotation(currentSorterAngle),
                PRIM_GLOW, ALL_SIDES, 0.0
            ]
        );

        if (progress >= 1.0) finishAction();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
    }
}
