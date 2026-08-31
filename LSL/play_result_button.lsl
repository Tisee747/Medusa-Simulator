// Play-result button: request playback of the active submitted attempt.
integer MASTER_CHANNEL = -451200;

setHover()
{
    llSetText("PLAY MY RESULT", <0.20, 0.65, 1.00>, 1.0);
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
        llRegionSay(MASTER_CHANNEL, "BTN_PLAY");
        llRegionSayTo(avatar, 0, "MEDUSA: Playing your latest submitted result...");
    }
}
