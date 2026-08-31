// Displays the simulator web UI on a dedicated white cube-prim screen.

integer MASTER_CHANNEL = -451200;
// Configure privately for the target deployment; keep infrastructure URLs out of source control.
string HOME_URL = "";
string BLANK_TEXTURE = "5748decc-f629-461c-9a36-a35a221fe21f";

integer mediaFace = -1;
integer listenHandle;

prepareScreen()
{
    if (mediaFace < 0)
        return;

    // A blank white texture plus Full Bright prevents the screen from inheriting dark mesh materials.
    llSetLinkPrimitiveParamsFast(
        LINK_THIS,
        [
            PRIM_TEXTURE, mediaFace, BLANK_TEXTURE, <1.0, 1.0, 0.0>, ZERO_VECTOR, 0.0,
            PRIM_COLOR, mediaFace, <1.0, 1.0, 1.0>, 1.0,
            PRIM_FULLBRIGHT, mediaFace, TRUE,
            PRIM_GLOW, mediaFace, 0.0,
            PRIM_BUMP_SHINY, mediaFace, PRIM_SHINY_NONE, PRIM_BUMP_NONE
        ]
    );
}

loadSavedFace()
{
    string description = llGetObjectDesc();
    if (llSubStringIndex(description, "MEDIA_FACE=") == 0)
    {
        mediaFace = (integer)llGetSubString(description, 11, -1);
        if (mediaFace < 0 || mediaFace >= llGetNumberOfSides())
            mediaFace = -1;
    }
}

saveFace(integer face)
{
    mediaFace = face;
    llSetObjectDesc("MEDIA_FACE=" + (string)face);
}

clearAllMedia()
{
    integer face;
    integer totalFaces = llGetNumberOfSides();
    for (face = 0; face < totalFaces; face++)
        llClearPrimMedia(face);
}

loadPage(string url)
{
    if (mediaFace < 0)
    {
        llOwnerSay("Sentuh permukaan depan cube monitor untuk memilih face media.");
        return;
    }

    if (url == "")
        url = HOME_URL;

    prepareScreen();

    integer result = llSetPrimMediaParams(
        mediaFace,
        [
            PRIM_MEDIA_CURRENT_URL, url,
            PRIM_MEDIA_HOME_URL, url,
            PRIM_MEDIA_AUTO_PLAY, TRUE,
            PRIM_MEDIA_AUTO_SCALE, TRUE,
            PRIM_MEDIA_AUTO_ZOOM, FALSE,
            PRIM_MEDIA_FIRST_CLICK_INTERACT, TRUE,
            PRIM_MEDIA_CONTROLS, PRIM_MEDIA_CONTROLS_STANDARD,
            PRIM_MEDIA_WIDTH_PIXELS, 1280,
            PRIM_MEDIA_HEIGHT_PIXELS, 720,
            PRIM_MEDIA_PERMS_INTERACT, PRIM_MEDIA_PERM_ANYONE,
            PRIM_MEDIA_PERMS_CONTROL, PRIM_MEDIA_PERM_ANYONE
        ]
    );

    if (result != 0)
        llOwnerSay("Gagal mengatur media monitor. Kode: " + (string)result);

    llSetTimerEvent(1.0);
}

processMessage(string message)
{
    list parts = llParseStringKeepNulls(message, ["|"], []);
    string command = llList2String(parts, 0);

    if (command == "OPEN_URL" || command == "EDITOR_URL")
        loadPage(llList2String(parts, 1));
    else if (command == "EDITOR_CLEAR" || command == "EDITOR_HOME")
        loadPage(HOME_URL);
}

default
{
    state_entry()
    {
        loadSavedFace();
        listenHandle = llListen(MASTER_CHANNEL, "", NULL_KEY, "");

        if (mediaFace >= 0)
            loadPage(HOME_URL);
        else
            llSetText("SENTUH DEPAN LAYAR", <0.25, 0.75, 1.0>, 1.0);

        // Ask the master to resend the page for the current backend state.
        llRegionSay(MASTER_CHANNEL, "MONITOR_READY");
    }

    touch_start(integer totalNumber)
    {
        integer touchedFace = llDetectedTouchFace(0);
        if (touchedFace < 0)
        {
            llOwnerSay("Face tidak terdeteksi. Sentuh langsung permukaan depan cube.");
            return;
        }

        clearAllMedia();
        saveFace(touchedFace);
        prepareScreen();
        llSetText("", ZERO_VECTOR, 0.0);
        loadPage(HOME_URL);
        llRegionSay(MASTER_CHANNEL, "MONITOR_READY");
    }

    listen(integer channel, string name, key id, string message)
    {
        if (channel == MASTER_CHANNEL && llGetOwnerKey(id) == llGetOwner())
            processMessage(message);
    }

    timer()
    {
        prepareScreen();
        llSetTimerEvent(0.0);
    }

    on_rez(integer startParameter)
    {
        llResetScript();
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
            llResetScript();
    }
}

