// Idle robot actor: manage the robot pose while the station is inactive.
integer MSG_EDIT = 9101;
integer MSG_CALIBRATE = 9102;
integer MSG_SHOW = 9103;
integer MSG_PLAY = 9104;
integer MSG_RESET = 9105;
integer MSG_HIDE = 9106;

string STATE_VERSION = "IDLE_V22";

string BASE_NAME = "idle_robot";
float TIMER_STEP = 0.10;
float TRAVEL_DISTANCE = 1.70;
float TRAVEL_SPEED = 0.55;
integer BATCH_SIZE = 8;

float RIGHT_HEADING = PI_BY_TWO;
float LEFT_HEADING = -PI_BY_TWO;

list memberLinks;
list homePositions;
list homeRotations;
integer anchorLink = 0;
integer anchorIndex = -1;
integer ready = FALSE;
integer playing = FALSE;
float timeValue = 0.0;

integer isMemberName(string value)
{
    string name = llToLower(llStringTrim(value, STRING_TRIM));
    string base = llToLower(BASE_NAME);

    if (name == base) return TRUE;
    if (llSubStringIndex(name, base + "#") == 0) return TRUE;
    if (llSubStringIndex(name, base + "__#") == 0) return TRUE;

    return FALSE;
}

integer discoverMembers()
{
    memberLinks = [];
    anchorLink = 0;
    anchorIndex = -1;

    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        string name = llGetLinkName(link);

        if (isMemberName(name))
        {
            if (llToLower(llStringTrim(name, STRING_TRIM)) == llToLower(BASE_NAME))
            {
                anchorLink = link;
                anchorIndex = llGetListLength(memberLinks);
            }

            memberLinks += [link];
        }
    }

    if (!llGetListLength(memberLinks))
    {
        llOwnerSay("IDLE ROBOT ERROR: grup idle_robot tidak ditemukan.");
        return FALSE;
    }

    if (!anchorLink)
    {
        llOwnerSay("IDLE ROBOT ERROR: anchor bernama persis idle_robot tidak ditemukan.");
        return FALSE;
    }

    return TRUE;
}

string rootMode()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);

    if (llGetListLength(fields) < 5) return "RECOVERY";
    if (llToUpper(llList2String(fields, 0)) != "HOME") return "RECOVERY";
    if (llToUpper(llList2String(fields, 1)) != STATE_VERSION) return "RECOVERY";

    return llToUpper(llList2String(fields, 4));
}

stopWithoutMoving()
{
    playing = FALSE;
    ready = FALSE;
    timeValue = 0.0;
    llSetTimerEvent(0.0);
    discoverMembers();
}

integer loadHome()
{
    if (!discoverMembers())
    {
        ready = FALSE;
        return FALSE;
    }

    list positions = [];
    list rotations = [];
    integer count = llGetListLength(memberLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(memberLinks, i);
        string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
        list fields = llParseStringKeepNulls(description, ["|"], []);

        if (
            llGetListLength(fields) < 4
            || llToUpper(llList2String(fields, 0)) != "HOME"
            || llToUpper(llList2String(fields, 1)) != STATE_VERSION
        )
        {
            ready = FALSE;
            llOwnerSay("IDLE ROBOT HOME BELUM LENGKAP: link " + (string)link + " " + llGetLinkName(link));
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

captureHome()
{
    playing = FALSE;
    llSetTimerEvent(0.0);

    if (!discoverMembers())
    {
        ready = FALSE;
        return;
    }

    homePositions = [];
    homeRotations = [];

    integer count = llGetListLength(memberLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(memberLinks, i);
        list data = llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
        vector position = llList2Vector(data, 0);
        rotation rot = llList2Rot(data, 1);

        homePositions += [position];
        homeRotations += [rot];

        llSetLinkPrimitiveParamsFast(
            link,
            [PRIM_DESC, "HOME|" + STATE_VERSION + "|" + (string)position + "|" + (string)rot]
        );
    }

    ready = TRUE;
    timeValue = 0.0;
    llOwnerSay("IDLE ROBOT CALIBRATED: " + (string)count + " prim.");
}

applyPose(float travel, rotation deltaRotation)
{
    if (!ready || anchorIndex < 0) return;

    vector pivot = llList2Vector(homePositions, anchorIndex);
    integer count = llGetListLength(memberLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(memberLinks, i);
        vector basePosition = llList2Vector(homePositions, i);
        rotation baseRotation = llList2Rot(homeRotations, i);
        vector offset = basePosition - pivot;
        vector newPosition = pivot + <travel, 0.0, 0.0> + (offset * deltaRotation);
        rotation newRotation = baseRotation * deltaRotation;

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

    if (llGetListLength(rules))
    {
        llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
    }
}

resetActor()
{
    playing = FALSE;
    llSetTimerEvent(0.0);
    timeValue = 0.0;

    if (rootMode() == "RECOVERY")
    {
        stopWithoutMoving();
        return;
    }

    if (loadHome())
    {
        applyPose(0.0, ZERO_ROTATION);
    }
}

startActor()
{
    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("IDLE ROBOT PLAY DITOLAK: HOME root belum valid.");
        stopWithoutMoving();
        return;
    }

    if (!loadHome())
    {
        llOwnerSay("IDLE ROBOT PLAY DITOLAK: jalankan EDIT lalu CALIBRATE.");
        return;
    }

    timeValue = 0.0;
    applyPose(0.0, llEuler2Rot(<0.0, 0.0, RIGHT_HEADING>));
    playing = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        playing = FALSE;

        string mode = rootMode();

        if (mode == "RECOVERY")
        {
            stopWithoutMoving();
            llOwnerSay("IDLE ROBOT RECOVERY: posisi tidak diubah dan pose belum disimpan.");
        }
        else if (mode == "EDIT")
        {
            captureHome();
            llOwnerSay("IDLE ROBOT AUTO-CALIBRATE: Reset Scripts saat EDIT.");
        }
        else
        {
            resetActor();
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
            if (rootMode() == "RECOVERY") stopWithoutMoving();
            else resetActor();
        }
        else if (number == MSG_SHOW || number == MSG_RESET || number == MSG_HIDE)
        {
            resetActor();
        }
        else if (number == MSG_PLAY)
        {
            startActor();
        }
    }

    timer()
    {
        if (!playing || !ready) return;

        float legDuration = TRAVEL_DISTANCE / TRAVEL_SPEED;
        float cycleDuration = legDuration * 2.0;

        timeValue += TIMER_STEP;

        if (timeValue >= cycleDuration)
        {
            timeValue -= cycleDuration;
        }

        float travel;
        float heading;

        if (timeValue < legDuration)
        {
            travel = timeValue * TRAVEL_SPEED;
            if (travel > TRAVEL_DISTANCE) travel = TRAVEL_DISTANCE;
            heading = RIGHT_HEADING;
        }
        else
        {
            float returnTime = timeValue - legDuration;
            travel = TRAVEL_DISTANCE - (returnTime * TRAVEL_SPEED);
            if (travel < 0.0) travel = 0.0;
            heading = LEFT_HEADING;
        }

        applyPose(travel, llEuler2Rot(<0.0, 0.0, heading>));
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
