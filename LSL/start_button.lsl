// Start button: begin a new simulator session for the active avatar.
integer MASTER_CHANNEL = -451200;

setHover()
{
    llSetText("START", <0.20, 1.00, 0.35>, 1.0);
}

default
{
    state_entry()
    {
        setHover();
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER) llResetScript();
    }

    touch_start(integer totalNumber)
    {
        key avatar = llDetectedKey(0);
        string avatarName = llKey2Name(avatar);

        llRegionSay(
            MASTER_CHANNEL,
            "BTN_START|" + (string)avatar + "|" + avatarName
        );

        llRegionSayTo(avatar, 0, "MEDUSA: Starting your session...");
    }
}
