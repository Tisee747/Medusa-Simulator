// Idle scene block actor: respond to visibility and playback commands.
integer MSG_EDIT = 9101;
integer MSG_CALIBRATE = 9102;
integer MSG_SHOW = 9103;
integer MSG_PLAY = 9104;
integer MSG_RESET = 9105;
integer MSG_HIDE = 9106;

string STATE_VERSION = "IDLE_V22";

float TIMER_STEP = 0.10;
float MOVE_AMOUNT = 0.035;
float MOVE_SPEED = 1.10;
integer BATCH_SIZE = 8;

list memberLinks;
list memberGroups;
list homePositions;
list homeRotations;
integer ready = FALSE;
integer playing = FALSE;
float timeValue = 0.0;

integer matchesBase(string value, string base)
{
    string name = llToLower(llStringTrim(value, STRING_TRIM));
    base = llToLower(base);

    if (name == base) return TRUE;
    if (llSubStringIndex(name, base + "#") == 0) return TRUE;
    if (llSubStringIndex(name, base + "__#") == 0) return TRUE;

    return FALSE;
}

integer groupForName(string value)
{
    if (matchesBase(value, "if_block")) return 0;
    if (matchesBase(value, "loop_block")) return 1;
    if (matchesBase(value, "function_block")) return 2;
    return -1;
}

integer discoverMembers()
{
    memberLinks = [];
    memberGroups = [];

    integer foundIf = FALSE;
    integer foundLoop = FALSE;
    integer foundFunction = FALSE;
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        integer group = groupForName(llGetLinkName(link));

        if (group >= 0)
        {
            memberLinks += [link];
            memberGroups += [group];

            if (group == 0) foundIf = TRUE;
            else if (group == 1) foundLoop = TRUE;
            else if (group == 2) foundFunction = TRUE;
        }
    }

    if (!foundIf) llOwnerSay("IDLE BLOCKS ERROR: grup if_block tidak ditemukan.");
    if (!foundLoop) llOwnerSay("IDLE BLOCKS ERROR: grup loop_block tidak ditemukan.");
    if (!foundFunction) llOwnerSay("IDLE BLOCKS ERROR: grup function_block tidak ditemukan.");

    return foundIf && foundLoop && foundFunction;
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
            llOwnerSay("IDLE BLOCKS HOME BELUM LENGKAP: link " + (string)link + " " + llGetLinkName(link));
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
    llOwnerSay("IDLE BLOCKS CALIBRATED: " + (string)count + " prim.");
}

applyMovement(float phase)
{
    if (!ready) return;

    integer count = llGetListLength(memberLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(memberLinks, i);
        integer group = llList2Integer(memberGroups, i);
        vector basePosition = llList2Vector(homePositions, i);
        rotation baseRotation = llList2Rot(homeRotations, i);
        float offsetPhase = 0.0;

        if (group == 1) offsetPhase = 2.094395;
        else if (group == 2) offsetPhase = 4.188790;

        float movement = llSin(phase + offsetPhase) * MOVE_AMOUNT;
        vector newPosition = basePosition + <0.0, 0.0, movement>;

        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, newPosition,
            PRIM_ROT_LOCAL, baseRotation
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
        integer count = llGetListLength(memberLinks);
        integer i;
        list rules = [];
        integer batchCount = 0;

        for (i = 0; i < count; i++)
        {
            integer link = llList2Integer(memberLinks, i);

            rules += [
                PRIM_LINK_TARGET, link,
                PRIM_POS_LOCAL, llList2Vector(homePositions, i),
                PRIM_ROT_LOCAL, llList2Rot(homeRotations, i)
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
}

startActor()
{
    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("IDLE BLOCKS PLAY DITOLAK: HOME root belum valid.");
        stopWithoutMoving();
        return;
    }

    if (!loadHome())
    {
        llOwnerSay("IDLE BLOCKS PLAY DITOLAK: jalankan EDIT lalu CALIBRATE.");
        return;
    }

    timeValue = 0.0;
    resetActor();
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
            llOwnerSay("IDLE BLOCKS RECOVERY: posisi tidak diubah dan pose belum disimpan.");
        }
        else if (mode == "EDIT")
        {
            captureHome();
            llOwnerSay("IDLE BLOCKS AUTO-CALIBRATE: Reset Scripts saat EDIT.");
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

        timeValue += TIMER_STEP;
        applyMovement(timeValue * MOVE_SPEED);
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
