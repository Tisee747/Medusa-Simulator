// Reset button: cancel the current station attempt and animation state.
integer MASTER_CHANNEL = -451200;

setHover()
{
    llSetText("RESET", <1.00, 0.55, 0.10>, 1.0);
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
        llRegionSay(MASTER_CHANNEL, "BTN_RESET");
        llRegionSayTo(avatar, 0, "MEDUSA: Resetting the active scene...");
    }
}
