// Parking display actor: show validated parking results on the scene display.
integer MSG_EDIT = 9401;
integer MSG_CALIBRATE = 9402;
integer MSG_SHOW = 9403;
integer MSG_RESET = 9404;
integer MSG_HIDE = 9405;
integer MSG_DISPLAY_SET = 9430;
integer MSG_GATE_STATE = 9431;

list displayLinks = [];
list redLinks = [];
list greenLinks = [];

string lower(string value)
{
    return llToLower(llStringTrim(value, STRING_TRIM));
}

integer startsWith(string value, string prefix)
{
    return llSubStringIndex(value, prefix) == 0;
}

integer memberName(string name, string base)
{
    return (
        name == base
        || startsWith(name, base + "#")
        || startsWith(name, base + "__#")
    );
}

discoverLinks()
{
    displayLinks = [];
    redLinks = [];
    greenLinks = [];

    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        string name = lower(llGetLinkName(link));

        if (memberName(name, "parking_display")) displayLinks += [link];
        else if (memberName(name, "gate_red_light")) redLinks += [link];
        else if (memberName(name, "gate_green_light")) greenLinks += [link];
    }
}

setLinkColor(list links, vector color, integer fullBright, float glow)
{
    integer count = llGetListLength(links);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(links, i);
        llSetLinkPrimitiveParamsFast(
            link,
            [
                PRIM_COLOR, ALL_SIDES, color, 1.0,
                PRIM_FULLBRIGHT, ALL_SIDES, fullBright,
                PRIM_GLOW, ALL_SIDES, glow
            ]
        );
    }
}

setDisplay(string text)
{
    discoverLinks();

    if (!llGetListLength(displayLinks))
    {
        llSetText(text, <1.0, 1.0, 1.0>, 1.0);
        return;
    }

    llSetText("", ZERO_VECTOR, 0.0);

    integer count = llGetListLength(displayLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        llSetLinkPrimitiveParamsFast(
            llList2Integer(displayLinks, i),
            [PRIM_TEXT, text, <1.0, 1.0, 1.0>, 1.0]
        );
    }
}

setGate(string gateMode)
{
    gateMode = llToUpper(llStringTrim(gateMode, STRING_TRIM));
    discoverLinks();

    vector redColor = <0.18, 0.0, 0.0>;
    vector greenColor = <0.0, 0.12, 0.0>;
    integer redBright = FALSE;
    integer greenBright = FALSE;
    float redGlow = 0.0;
    float greenGlow = 0.0;

    if (gateMode == "OPEN" || gateMode == "OPENING")
    {
        greenColor = <0.0, 1.0, 0.10>;
        greenBright = TRUE;
        greenGlow = 0.20;
    }
    else
    {
        redColor = <1.0, 0.02, 0.02>;
        redBright = TRUE;
        redGlow = 0.20;
    }

    setLinkColor(redLinks, redColor, redBright, redGlow);
    setLinkColor(greenLinks, greenColor, greenBright, greenGlow);
}

resetDisplay()
{
    setDisplay("");
    setGate("CLOSED");
}

default
{
    state_entry()
    {
        discoverLinks();
        resetDisplay();

        llOwnerSay(
            "PARKING DISPLAY READY: display=" + (string)llGetListLength(displayLinks)
            + ", red=" + (string)llGetListLength(redLinks)
            + ", green=" + (string)llGetListLength(greenLinks) + "."
        );
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_DISPLAY_SET)
        {
            setDisplay(message);
        }
        else if (number == MSG_GATE_STATE)
        {
            setGate(message);
        }
        else if (number == MSG_RESET || number == MSG_HIDE)
        {
            resetDisplay();
        }
        else if (number == MSG_EDIT)
        {
            setDisplay("EDIT MODE");
            setGate("CLOSED");
        }
        else if (number == MSG_CALIBRATE)
        {
            setDisplay("CALIBRATED");
            setGate("CLOSED");
        }
        else if (number == MSG_SHOW)
        {
            setDisplay("PARKING READY");
            setGate("CLOSED");
        }
    }

    changed(integer change)
    {
        if (change & (CHANGED_LINK | CHANGED_OWNER))
        {
            llResetScript();
        }
    }
}
