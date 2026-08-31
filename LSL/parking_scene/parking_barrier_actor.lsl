// Parking barrier actor: enforce the barrier's scene commands safely.
integer MSG_EDIT = 9401;
integer MSG_CALIBRATE = 9402;
integer MSG_SHOW = 9403;
integer MSG_RESET = 9404;
integer MSG_HIDE = 9405;
integer MSG_BARRIER_ACTION = 9420;
integer MSG_BARRIER_DONE = 9421;

string STATE_VERSION = "PARKING_V21";
float TIMER_STEP = 0.025;
float MOVE_TIME = 0.90;
float OPEN_ANGLE = 78.0 * DEG_TO_RAD;
integer BATCH_SIZE = 8;

integer pivotLink = 0;
integer hingeLink = 0;
list movingLinks = [];
list storedLinks = [];
list homePositions = [];
list homeRotations = [];
vector pivotPosition = ZERO_VECTOR;
vector rotationAxis = <1.0, 0.0, 0.0>;
integer ready = FALSE;
integer moving = FALSE;
float currentProgress = 0.0;
float startProgress = 0.0;
float targetProgress = 0.0;
float elapsed = 0.0;
string pendingAction = "";

string lower(string value)
{
    return llToLower(llStringTrim(value, STRING_TRIM));
}

string upper(string value)
{
    return llToUpper(llStringTrim(value, STRING_TRIM));
}

integer startsWith(string value, string prefix)
{
    return llSubStringIndex(value, prefix) == 0;
}

string rootMode()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);

    if (llGetListLength(fields) < 5) return "RECOVERY";
    if (upper(llList2String(fields, 0)) != "HOME") return "RECOVERY";
    if (upper(llList2String(fields, 1)) != STATE_VERSION) return "RECOVERY";

    return upper(llList2String(fields, 4));
}

integer findExact(string target)
{
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        if (lower(llGetLinkName(link)) == lower(target)) return link;
    }

    return 0;
}

float longestDimension(integer link)
{
    vector size = llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_SIZE]), 0);
    float longest = size.x;
    if (size.y > longest) longest = size.y;
    if (size.z > longest) longest = size.z;
    return longest;
}

integer discoverKnownLayout()
{
    pivotLink = 0;
    hingeLink = 0;
    movingLinks = [];

    integer knownArm = findExact("barrier_arm_vpark");

    if (knownArm)
    {
        pivotLink = findExact("barrier_arm");
        hingeLink = findExact("barrier_arm_vpark#1");

        integer count = llGetNumberOfPrims();
        integer link;

        for (link = 1; link <= count; link++)
        {
            string name = lower(llGetLinkName(link));

            if (
                name == "barrier_arm_vpark"
                || startsWith(name, "barrier_arm_vpark__#")
                || (startsWith(name, "barrier_arm_vpark#") && name != "barrier_arm_vpark#1")
            )
            {
                movingLinks += [link];
            }
        }

        return TRUE;
    }

    integer namedBar = findExact("barrier_bar");

    if (namedBar)
    {
        pivotLink = findExact("barrier_pivot");
        hingeLink = findExact("barrier_hinge");

        integer count2 = llGetNumberOfPrims();
        integer link2;

        for (link2 = 1; link2 <= count2; link2++)
        {
            string name2 = lower(llGetLinkName(link2));
            if (name2 == "barrier_bar" || startsWith(name2, "barrier_bar#") || startsWith(name2, "barrier_bar__#"))
            {
                movingLinks += [link2];
            }
        }

        return TRUE;
    }

    integer numberedBar = findExact("barrier_arm#3");

    if (numberedBar)
    {
        pivotLink = findExact("barrier_arm");
        hingeLink = findExact("barrier_arm#2");
        movingLinks = [numberedBar];
        return TRUE;
    }

    return FALSE;
}

integer discoverFallbackLayout()
{
    list candidates = [];
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        string name = lower(llGetLinkName(link));
        if (name == "barrier_arm" || startsWith(name, "barrier_arm#") || startsWith(name, "barrier_arm__#"))
        {
            candidates += [link];
        }
    }

    integer candidateCount = llGetListLength(candidates);
    if (candidateCount < 2) return FALSE;

    integer longestLink = 0;
    float longestSize = 0.0;
    integer i;

    for (i = 0; i < candidateCount; i++)
    {
        integer candidate = llList2Integer(candidates, i);
        float dimension = longestDimension(candidate);

        if (dimension > longestSize)
        {
            longestSize = dimension;
            longestLink = candidate;
        }
    }

    movingLinks = [longestLink];

    integer exactBase = findExact("barrier_arm");
    if (exactBase && exactBase != longestLink) pivotLink = exactBase;

    for (i = 0; i < candidateCount; i++)
    {
        integer remaining = llList2Integer(candidates, i);

        if (remaining != longestLink && remaining != pivotLink)
        {
            hingeLink = remaining;
            i = candidateCount;
        }
    }

    if (!pivotLink)
    {
        for (i = 0; i < candidateCount; i++)
        {
            integer remaining2 = llList2Integer(candidates, i);
            if (remaining2 != longestLink && remaining2 != hingeLink)
            {
                pivotLink = remaining2;
                i = candidateCount;
            }
        }
    }

    return pivotLink != 0;
}


string hingeName()
{
    if (hingeLink) return llGetLinkName(hingeLink);
    return "NONE";
}

integer discoverMembers()
{
    pivotLink = 0;
    hingeLink = 0;
    movingLinks = [];
    storedLinks = [];

    integer found = discoverKnownLayout();
    if (!found) found = discoverFallbackLayout();

    if (!found || !pivotLink || !llGetListLength(movingLinks))
    {
        llOwnerSay("PARKING BARRIER ERROR: pivot atau batang barrier tidak ditemukan.");
        return FALSE;
    }

    storedLinks = [pivotLink];
    if (hingeLink) storedLinks += [hingeLink];
    storedLinks += movingLinks;

    llOwnerSay(
        "PARKING BARRIER LINKS: pivot=" + llGetLinkName(pivotLink)
        + ", hinge=" + hingeName()
        + ", moving=" + (string)llGetListLength(movingLinks)
    );

    return TRUE;
}

integer storedIndex(integer link)
{
    return llListFindList(storedLinks, [link]);
}

integer validHomeDescription(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);

    return (
        llGetListLength(fields) >= 4
        && upper(llList2String(fields, 0)) == "HOME"
        && upper(llList2String(fields, 1)) == STATE_VERSION
    );
}

vector homePositionFor(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);
    return (vector)llList2String(fields, 2);
}

rotation homeRotationFor(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);
    return (rotation)llList2String(fields, 3);
}

integer loadHome()
{
    if (!discoverMembers())
    {
        ready = FALSE;
        return FALSE;
    }

    homePositions = [];
    homeRotations = [];

    integer count = llGetListLength(storedLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(storedLinks, i);

        if (!validHomeDescription(link))
        {
            llOwnerSay("PARKING BARRIER HOME BELUM LENGKAP: " + llGetLinkName(link));
            ready = FALSE;
            return FALSE;
        }

        homePositions += [homePositionFor(link)];
        homeRotations += [homeRotationFor(link)];
    }

    integer pivotIndex = storedIndex(pivotLink);
    pivotPosition = llList2Vector(homePositions, pivotIndex);

    if (hingeLink)
    {
        integer hingeIndex = storedIndex(hingeLink);
        pivotPosition = llList2Vector(homePositions, hingeIndex);
    }

    float farthest = 0.0;
    vector reference = pivotPosition + <0.0, -1.0, 0.0>;
    integer movingCount = llGetListLength(movingLinks);

    for (i = 0; i < movingCount; i++)
    {
        integer movingLink = llList2Integer(movingLinks, i);
        integer index = storedIndex(movingLink);
        vector position = llList2Vector(homePositions, index);
        vector horizontal = position - pivotPosition;
        horizontal.z = 0.0;
        float distance = llVecMag(horizontal);

        if (distance > farthest)
        {
            farthest = distance;
            reference = position;
        }
    }

    vector direction = reference - pivotPosition;
    direction.z = 0.0;

    if (llVecMag(direction) < 0.10) direction = <0.0, -1.0, 0.0>;
    direction = llVecNorm(direction);
    rotationAxis = llVecNorm(<direction.y, -direction.x, 0.0>);

    integer testLink = llList2Integer(movingLinks, 0);
    integer testIndex = storedIndex(testLink);
    vector testPosition = llList2Vector(homePositions, testIndex);
    vector testOffset = testPosition - pivotPosition;
    rotation testRotation = llAxisAngle2Rot(rotationAxis, 10.0 * DEG_TO_RAD);
    vector raisedTest = pivotPosition + (testOffset * testRotation);

    if (raisedTest.z < testPosition.z)
    {
        rotationAxis = rotationAxis * -1.0;
    }

    ready = TRUE;
    return TRUE;
}

captureHome()
{
    moving = FALSE;
    llSetTimerEvent(0.0);

    if (!discoverMembers())
    {
        ready = FALSE;
        return;
    }

    integer count = llGetListLength(storedLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(storedLinks, i);
        list data = llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
        vector position = llList2Vector(data, 0);
        rotation rot = llList2Rot(data, 1);

        llSetLinkPrimitiveParamsFast(
            link,
            [PRIM_DESC, "HOME|" + STATE_VERSION + "|" + (string)position + "|" + (string)rot]
        );
    }

    ready = FALSE;
    currentProgress = 0.0;
    loadHome();
    llOwnerSay("PARKING BARRIER CALIBRATED: pivot/hinge statis dan batang tersimpan.");
}


restoreStaticParts()
{
    if (!ready) return;

    list staticLinks = [pivotLink];
    if (hingeLink) staticLinks += [hingeLink];

    integer count = llGetListLength(staticLinks);
    list rules = [];
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(staticLinks, i);
        integer index = storedIndex(link);

        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, llList2Vector(homePositions, index),
            PRIM_ROT_LOCAL, llList2Rot(homeRotations, index)
        ];
    }

    llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
}

applyProgress(float progress)
{
    if (!ready) return;

    float eased = progress * progress * (3.0 - 2.0 * progress);
    rotation delta = llAxisAngle2Rot(rotationAxis, OPEN_ANGLE * eased);
    integer count = llGetListLength(movingLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    restoreStaticParts();

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(movingLinks, i);
        integer index = storedIndex(link);
        vector basePosition = llList2Vector(homePositions, index);
        rotation baseRotation = llList2Rot(homeRotations, index);
        vector offset = basePosition - pivotPosition;
        vector newPosition = pivotPosition + (offset * delta);
        rotation newRotation = baseRotation * delta;

        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, newPosition,
            PRIM_ROT_LOCAL, newRotation
        ];
        batchCount++;

        if (batchCount >= BATCH_SIZE)
        {
            llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
            rules = [];
            batchCount = 0;
        }
    }

    if (llGetListLength(rules)) llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
}

resetBarrier()
{
    moving = FALSE;
    currentProgress = 0.0;
    targetProgress = 0.0;
    elapsed = 0.0;
    llSetTimerEvent(0.0);

    if (rootMode() == "RECOVERY")
    {
        ready = FALSE;
        discoverMembers();
        return;
    }

    if (loadHome()) applyProgress(0.0);
}

startBarrier(string action)
{
    action = upper(action);

    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("PARKING BARRIER ACTION DITOLAK: HOME belum valid.");
        return;
    }

    if (!ready && !loadHome()) return;

    pendingAction = action;
    startProgress = currentProgress;
    targetProgress = 0.0;
    if (action == "OPEN") targetProgress = 1.0;

    if (llFabs(targetProgress - currentProgress) < 0.001)
    {
        llMessageLinked(LINK_SET, MSG_BARRIER_DONE, action, NULL_KEY);
        return;
    }

    elapsed = 0.0;
    moving = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        string currentMode = rootMode();

        if (currentMode == "RECOVERY")
        {
            moving = FALSE;
            ready = FALSE;
            discoverMembers();
            llOwnerSay("PARKING BARRIER RECOVERY V2: posisi tidak diubah dan HOME belum disimpan.");
        }
        else if (currentMode == "EDIT")
        {
            captureHome();
            llOwnerSay("PARKING BARRIER AUTO-CALIBRATE: Reset Scripts saat EDIT.");
        }
        else
        {
            resetBarrier();
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
            if (rootMode() == "RECOVERY")
            {
                moving = FALSE;
                llSetTimerEvent(0.0);
                discoverMembers();
            }
            else
            {
                resetBarrier();
            }
        }
        else if (number == MSG_SHOW || number == MSG_RESET || number == MSG_HIDE)
        {
            resetBarrier();
        }
        else if (number == MSG_BARRIER_ACTION)
        {
            startBarrier(message);
        }
    }

    timer()
    {
        if (!moving || !ready) return;

        elapsed += TIMER_STEP;
        float progress = elapsed / MOVE_TIME;

        if (progress >= 1.0)
        {
            progress = 1.0;
            moving = FALSE;
        }

        currentProgress = startProgress + (targetProgress - startProgress) * progress;
        applyProgress(currentProgress);

        if (!moving)
        {
            llSetTimerEvent(0.0);
            currentProgress = targetProgress;
            llMessageLinked(LINK_SET, MSG_BARRIER_DONE, pendingAction, NULL_KEY);
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
