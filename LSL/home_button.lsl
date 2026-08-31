// Home button: return the simulator station to its idle state.
integer MASTER_CHANNEL = -451200;

setHover()
{
    llSetText("HOME", <0.70, 0.35, 1.00>, 1.0);
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
        llRegionSay(MASTER_CHANNEL, "BTN_HOME");
        llRegionSayTo(avatar, 0, "MEDUSA: Returning home...");
    }
}
