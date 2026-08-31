// Leaderboard display: refresh the web surface at a controlled interval.
integer MEDIA_FACE = 1;
integer CONTROL_CHANNEL = -451298;

float AUTO_REFRESH_SECONDS = 30.0;

// Configure privately for the target deployment; keep infrastructure URLs out of source control.
string LEADERBOARD_URL = "";

string mediaUrl()
{
    return LEADERBOARD_URL + "?v=auto-" + (string)llGetUnixTime();
}

resetFaceMapping()
{
    llSetLinkPrimitiveParamsFast(
        LINK_THIS,
        [
            PRIM_TEXGEN, MEDIA_FACE, PRIM_TEXGEN_DEFAULT,
            PRIM_TEXTURE, MEDIA_FACE, TEXTURE_BLANK,
                <1.0, 1.0, 0.0>,
                <0.0, 0.0, 0.0>,
                0.0,
            PRIM_COLOR, MEDIA_FACE, <1.0, 1.0, 1.0>, 1.0,
            PRIM_FULLBRIGHT, MEDIA_FACE, TRUE
        ]
    );
}

integer installMedia(integer announce)
{
    string url = mediaUrl();

    resetFaceMapping();
    llClearPrimMedia(MEDIA_FACE);

    integer status = llSetPrimMediaParams(
        MEDIA_FACE,
        [
            PRIM_MEDIA_CURRENT_URL, url,
            PRIM_MEDIA_HOME_URL, url,
            PRIM_MEDIA_AUTO_PLAY, TRUE,
            PRIM_MEDIA_AUTO_SCALE, TRUE,
            PRIM_MEDIA_FIRST_CLICK_INTERACT, FALSE,
            PRIM_MEDIA_CONTROLS, PRIM_MEDIA_CONTROLS_MINI,
            PRIM_MEDIA_WIDTH_PIXELS, 1280,
            PRIM_MEDIA_HEIGHT_PIXELS, 720,
            PRIM_MEDIA_PERMS_INTERACT, PRIM_MEDIA_PERM_ANYONE,
            PRIM_MEDIA_PERMS_CONTROL, PRIM_MEDIA_PERM_OWNER
        ]
    );

    if (announce)
    {
        if (status == 0)
        {
            llOwnerSay(
                "LEADERBOARD AUTO REFRESH OK: setiap "
                + (string)((integer)AUTO_REFRESH_SECONDS)
                + " detik."
            );
        }
        else
        {
            llOwnerSay(
                "LEADERBOARD MEDIA ERROR: status="
                + (string)status
            );
        }
    }

    return status == 0;
}

default
{
    state_entry()
    {
        llSetClickAction(CLICK_ACTION_TOUCH);
        llListen(CONTROL_CHANNEL, "", llGetOwner(), "");

        installMedia(TRUE);
        llSetTimerEvent(AUTO_REFRESH_SECONDS);
    }

    timer()
    {
        installMedia(FALSE);
    }

    touch_start(integer totalNumber)
    {
        if (llDetectedKey(0) == llGetOwner())
        {
            installMedia(TRUE);
        }
    }

    listen(
        integer channel,
        string name,
        key speaker,
        string message
    )
    {
        if (channel != CONTROL_CHANNEL) return;
        if (speaker != llGetOwner()) return;

        message = llToUpper(
            llStringTrim(message, STRING_TRIM)
        );

        if (message == "REFRESH")
        {
            installMedia(TRUE);
        }
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }

    changed(integer change)
    {
        if (change & (CHANGED_OWNER | CHANGED_SHAPE))
        {
            llResetScript();
        }
    }
}

