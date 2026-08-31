// Traffic-light actor: display validated signal state changes.
string STATE_VERSION = "TRAFFIC_V1";

integer MSG_EDIT = 9201;
integer MSG_CALIBRATE = 9202;
integer MSG_SHOW = 9203;
integer MSG_RESULT = 9204;
integer MSG_RESET = 9205;
integer MSG_HIDE = 9206;
integer MSG_CANCEL = 9207;
integer MSG_RESULT_SEQ = 9208;
integer MSG_STEP_LIGHT = 9209;

string RED_BASE = "red_light";
string YELLOW_BASE = "yellow_light";
string GREEN_BASE = "green_light";

string RED_COMPANION = "traffic_light#5";
string YELLOW_COMPANION = "traffic_light#6";
string GREEN_COMPANION = "traffic_light#10";

vector RED_COLOR = <1.000, 0.020, 0.020>;
vector YELLOW_COLOR = <1.000, 0.750, 0.020>;
vector GREEN_COLOR = <0.020, 1.000, 0.050>;

float ACTIVE_GLOW = 0.45;
float ACTIVE_ALPHA = 1.0;
float INACTIVE_ALPHA = 1.0;
vector OFF_COLOR = <0.005, 0.005, 0.005>;
integer BATCH_SIZE = 8;

list lightLinks;
list lightGroups;
list homePositions;
list homeRotations;
integer ready = FALSE;

integer matchesBase(string value, string baseValue)
{
    string name = llToLower(llStringTrim(value, STRING_TRIM));
    string base = llToLower(llStringTrim(baseValue, STRING_TRIM));

    if (name == base) return TRUE;
    if (llSubStringIndex(name, base + "#") == 0) return TRUE;
    if (llSubStringIndex(name, base + "__#") == 0) return TRUE;

    return FALSE;
}

string groupForName(string value)
{
    string name = llToLower(llStringTrim(value, STRING_TRIM));

    if (matchesBase(name, RED_BASE)) return "RED";
    if (matchesBase(name, YELLOW_BASE)) return "YELLOW";
    if (matchesBase(name, GREEN_BASE)) return "GREEN";

    if (name == llToLower(RED_COMPANION)) return "RED";
    if (name == llToLower(YELLOW_COMPANION)) return "YELLOW";
    if (name == llToLower(GREEN_COMPANION)) return "GREEN";

    return "";
}

integer discoverLights()
{
    lightLinks = [];
    lightGroups = [];

    integer redCount = 0;
    integer yellowCount = 0;
    integer greenCount = 0;
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        string group = groupForName(llGetLinkName(link));

        if (group != "")
        {
            lightLinks += [link];
            lightGroups += [group];

            if (group == "RED") redCount++;
            else if (group == "YELLOW") yellowCount++;
            else if (group == "GREEN") greenCount++;
        }
    }

    if (!redCount)
    {
        llOwnerSay("TRAFFIC LIGHT ERROR: red_light tidak ditemukan.");
        return FALSE;
    }

    if (!yellowCount)
    {
        llOwnerSay("TRAFFIC LIGHT ERROR: yellow_light tidak ditemukan.");
        return FALSE;
    }

    if (!greenCount)
    {
        llOwnerSay("TRAFFIC LIGHT ERROR: green_light tidak ditemukan.");
        return FALSE;
    }

    ready = TRUE;

    llOwnerSay(
        "TRAFFIC LIGHT LINKS: red=" + (string)redCount
        + ", yellow=" + (string)yellowCount
        + ", green=" + (string)greenCount + "."
    );

    return TRUE;
}

vector colorForGroup(string group)
{
    if (group == "RED") return RED_COLOR;
    if (group == "YELLOW") return YELLOW_COLOR;
    return GREEN_COLOR;
}

setLightState(integer link, string group, integer active)
{
    vector color = OFF_COLOR;
    integer fullbright = FALSE;
    float glow = 0.0;

    if (active)
    {
        color = colorForGroup(group);
        fullbright = TRUE;
        glow = ACTIVE_GLOW;
    }

    llSetLinkPrimitiveParamsFast(
        link,
        [
            PRIM_COLOR, ALL_SIDES, color, 1.0,
            PRIM_FULLBRIGHT, ALL_SIDES, fullbright,
            PRIM_GLOW, ALL_SIDES, glow
        ]
    );
}

turnAllOff()
{
    if (!ready && !discoverLights()) return;

    integer count = llGetListLength(lightLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        setLightState(
            llList2Integer(lightLinks, i),
            llList2String(lightGroups, i),
            FALSE
        );
    }

    llOwnerSay("TRAFFIC LIGHT STATE: semua lampu mati.");
}

showColor(string value)
{
    if (!ready && !discoverLights()) return;

    string requested = llToUpper(llStringTrim(value, STRING_TRIM));
    string wantedGroup = "";

    if (requested == "MERAH" || requested == "RED") wantedGroup = "RED";
    else if (requested == "KUNING" || requested == "YELLOW") wantedGroup = "YELLOW";
    else if (requested == "HIJAU" || requested == "GREEN") wantedGroup = "GREEN";

    if (wantedGroup == "")
    {
        llOwnerSay("TRAFFIC LIGHT ERROR: warna tidak dikenal: " + value);
        turnAllOff();
        return;
    }

    integer count = llGetListLength(lightLinks);
    integer activeCount = 0;
    integer hiddenCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(lightLinks, i);
        string group = llList2String(lightGroups, i);
        integer active = group == wantedGroup;

        setLightState(link, group, active);

        if (active) activeCount++;
        else hiddenCount++;
    }

    llOwnerSay(
        "TRAFFIC LIGHT STATE: " + wantedGroup
        + " | visible=" + (string)activeCount
        + " | invisible=" + (string)hiddenCount + "."
    );
}

captureHome()
{
    if (!discoverLights()) return;

    homePositions = [];
    homeRotations = [];

    integer count = llGetListLength(lightLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(lightLinks, i);
        list data = llGetLinkPrimitiveParams(
            link,
            [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]
        );

        vector position = llList2Vector(data, 0);
        rotation rot = llList2Rot(data, 1);

        homePositions += [position];
        homeRotations += [rot];

        llSetLinkPrimitiveParamsFast(
            link,
            [
                PRIM_DESC,
                "HOME|" + STATE_VERSION + "|"
                + (string)position + "|" + (string)rot
            ]
        );
    }

    llOwnerSay(
        "TRAFFIC LIGHTS CALIBRATED: "
        + (string)count + " prim lampu disimpan."
    );
}

integer loadHome()
{
    if (!discoverLights()) return FALSE;

    list positions = [];
    list rotations = [];
    integer count = llGetListLength(lightLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(lightLinks, i);
        string description = llList2String(
            llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0
        );
        list fields = llParseStringKeepNulls(description, ["|"], []);

        if (
            llGetListLength(fields) < 4
            || llToUpper(llList2String(fields, 0)) != "HOME"
            || llToUpper(llList2String(fields, 1)) != STATE_VERSION
        )
        {
            return FALSE;
        }

        positions += [(vector)llList2String(fields, 2)];
        rotations += [(rotation)llList2String(fields, 3)];
    }

    homePositions = positions;
    homeRotations = rotations;
    return TRUE;
}

restoreHomeIfAvailable()
{
    if (!loadHome()) return;

    integer count = llGetListLength(lightLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(lightLinks, i);

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

default
{
    state_entry()
    {
        ready = FALSE;

        if (discoverLights())
        {
            turnAllOff();
            llOwnerSay(
                "TRAFFIC LIGHTS V1.6 READY: mendukung RESULT tunggal dan perubahan lampu per step RESULT_SEQ."
            );
        }
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_CALIBRATE)
        {
            captureHome();
            turnAllOff();
        }
        else if (number == MSG_RESULT)
        {
            list parts = llParseStringKeepNulls(message, ["|"], []);

            if (llGetListLength(parts) < 5)
            {
                llOwnerSay("TRAFFIC LIGHT RESULT ERROR: payload tidak lengkap.");
                return;
            }

            showColor(llList2String(parts, 4));
        }
        else if (number == MSG_STEP_LIGHT)
        {
            showColor(message);
        }
        else if (number == MSG_CANCEL)
        {
            turnAllOff();
        }
        else if (number == MSG_EDIT)
        {
            restoreHomeIfAvailable();
            turnAllOff();
        }
        else if (
            number == MSG_SHOW
            || number == MSG_RESET
            || number == MSG_HIDE
        )
        {
            restoreHomeIfAvailable();
            turnAllOff();
        }
    }

    changed(integer change)
    {
        if (change & CHANGED_LINK)
        {
            ready = FALSE;
            discoverLights();
        }

        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
