// Traffic vehicle actor: animate vehicle behavior for the active result.
integer MASTER_CHANNEL = -451200;
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

string BASE_NAME = "car";
string START_MARKER_NAME = "marker_start";
string STOP_MARKER_NAME = "marker_stop";
string END_MARKER_NAME = "marker_end";

float TIMER_STEP = 0.08;
float STOP_SPEED = 4.00;
float CAUTION_SPEED = 4.00;
float GO_SPEED = 7.00;
float RED_LIGHT_LEAD = 0.25;
float STOP_HOLD = 0.80;
float INVALID_ACTION_HOLD = 0.80;
float TARGET_REACHED_HOLD = 0.20;
float TARGET_EPSILON = 0.02;
float ROUTE_EPSILON = 0.000001;
integer MAX_SEQUENCE_STEPS = 10;
integer BATCH_SIZE = 8;
integer DEBUG_SEQUENCE_STEPS = TRUE;

integer PHASE_IDLE = 0;
integer PHASE_MOVE = 1;
integer PHASE_SEQUENCE_HOLD = 2;

list memberLinks;
list homePositions;
list homeRotations;
integer anchorLink = 0;
integer anchorIndex = -1;
integer startMarkerLink = 0;
integer stopMarkerLink = 0;
integer endMarkerLink = 0;

integer ready = FALSE;
integer playing = FALSE;
integer runPhase = 0;
float elapsed = 0.0;
float duration = 1.0;
vector motionStart;
vector motionTarget;
string activeAttempt = "";
string activeAction = "";

integer sequenceMode = FALSE;
integer sequenceCount = 0;
integer sequenceIndex = 0;
list sequenceColors;
list sequenceActuals;
list sequenceExpecteds;
integer nextStopLightPrimed = FALSE;

integer isMemberName(string value)
{
    string name = llToLower(llStringTrim(value, STRING_TRIM));
    string base = llToLower(BASE_NAME);

    if (name == base) return TRUE;
    if (llSubStringIndex(name, base + "#") == 0) return TRUE;
    if (llSubStringIndex(name, base + "__#") == 0) return TRUE;

    return FALSE;
}

integer findExactLink(string target)
{
    string wanted = llToLower(llStringTrim(target, STRING_TRIM));
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        if (llToLower(llStringTrim(llGetLinkName(link), STRING_TRIM)) == wanted)
        {
            return link;
        }
    }

    return 0;
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

    startMarkerLink = findExactLink(START_MARKER_NAME);
    stopMarkerLink = findExactLink(STOP_MARKER_NAME);
    endMarkerLink = findExactLink(END_MARKER_NAME);

    if (!llGetListLength(memberLinks))
    {
        llOwnerSay("TRAFFIC VEHICLE ERROR: grup car tidak ditemukan.");
        return FALSE;
    }

    if (!anchorLink)
    {
        llOwnerSay("TRAFFIC VEHICLE ERROR: anchor bernama persis car tidak ditemukan.");
        return FALSE;
    }

    if (!startMarkerLink || !stopMarkerLink || !endMarkerLink)
    {
        llOwnerSay("TRAFFIC VEHICLE ERROR: marker_start, marker_stop, atau marker_end tidak ditemukan.");
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

vector localPosition(integer link)
{
    return llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL]), 0);
}

float smoothStep(float value)
{
    if (value <= 0.0) return 0.0;
    if (value >= 1.0) return 1.0;
    return value * value * (3.0 - (2.0 * value));
}

string normalizeAction(string value)
{
    string action = llToUpper(llStringTrim(value, STRING_TRIM));
    action = llDumpList2String(llParseString2List(action, [" ", "-"], []), "_");

    if (action == "BERHENTI" || action == "STOP" || action == "MERAH") return "STOP";
    if (action == "HATI_HATI" || action == "PELAN" || action == "SLOW" || action == "KUNING") return "CAUTION";
    if (action == "JALAN" || action == "GO" || action == "HIJAU") return "GO";

    return "UNKNOWN";
}

clearSequenceData()
{
    sequenceMode = FALSE;
    sequenceCount = 0;
    sequenceIndex = 0;
    sequenceColors = [];
    sequenceActuals = [];
    sequenceExpecteds = [];
    nextStopLightPrimed = FALSE;
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
            llOwnerSay("TRAFFIC VEHICLE HOME BELUM LENGKAP: link " + (string)link + " " + llGetLinkName(link));
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
    runPhase = PHASE_IDLE;
    llSetTimerEvent(0.0);
    activeAttempt = "";
    activeAction = "";
    clearSequenceData();

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
    elapsed = 0.0;
    llOwnerSay(
        "TRAFFIC VEHICLE CALIBRATED CURRENT POSITION: "
        + (string)count
        + " prim | NEW HOME anchor="
        + (string)llList2Vector(homePositions, anchorIndex)
    );
}

applyAnchorPosition(vector anchorPosition)
{
    if (!ready || anchorIndex < 0) return;

    vector homeAnchor = llList2Vector(homePositions, anchorIndex);
    vector delta = anchorPosition - homeAnchor;
    integer count = llGetListLength(memberLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(memberLinks, i);
        vector basePosition = llList2Vector(homePositions, i);
        rotation baseRotation = llList2Rot(homeRotations, i);

        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, basePosition + delta,
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

stopWithoutMoving()
{
    playing = FALSE;
    ready = FALSE;
    runPhase = PHASE_IDLE;
    elapsed = 0.0;
    activeAttempt = "";
    activeAction = "";
    clearSequenceData();
    llSetTimerEvent(0.0);
    discoverMembers();
}

cancelRun(integer restoreStart)
{
    playing = FALSE;
    runPhase = PHASE_IDLE;
    elapsed = 0.0;
    activeAttempt = "";
    activeAction = "";
    clearSequenceData();
    llSetTimerEvent(0.0);

    if (!restoreStart) return;
    if (rootMode() == "RECOVERY") return;

    if (!ready)
    {
        loadHome();
    }

    if (ready && anchorIndex >= 0)
    {
        applyAnchorPosition(llList2Vector(homePositions, anchorIndex));
    }
}

resetActor()
{
    cancelRun(FALSE);

    if (rootMode() == "RECOVERY")
    {
        stopWithoutMoving();
        return;
    }

    if (loadHome())
    {
        applyAnchorPosition(llList2Vector(homePositions, anchorIndex));
    }
}

finishAnimation()
{
    string completedAttempt = activeAttempt;

    playing = FALSE;
    runPhase = PHASE_IDLE;
    elapsed = 0.0;
    activeAttempt = "";
    activeAction = "";
    clearSequenceData();
    llSetTimerEvent(0.0);

    if (completedAttempt != "")
    {
        llRegionSay(MASTER_CHANNEL, "ANIMATION_DONE|" + completedAttempt);
    }
}

vector sequenceStartAnchor()
{
    return llList2Vector(homePositions, anchorIndex);
}

vector sequenceStopAnchor()
{
    // RESULT_SEQ harus berhenti tepat pada marker_stop aktual.
    // HOME hanya menentukan posisi awal sequence, bukan menggeser target marker.
    return localPosition(stopMarkerLink);
}

vector sequenceEndAnchor()
{
    // RESULT_SEQ harus berakhir tepat pada marker_end aktual.
    // HOME baru tidak boleh ikut menggeser posisi target marker_end.
    return localPosition(endMarkerLink);
}

float progressAlongRoute(vector position, vector homeAnchor, vector endAnchor)
{
    vector route = endAnchor - homeAnchor;
    float routeLengthSquared = route * route;

    if (routeLengthSquared <= ROUTE_EPSILON)
    {
        return 0.0;
    }

    return ((position - homeAnchor) * route) / routeLengthSquared;
}

debugSequenceStepStart(vector position)
{
    if (!DEBUG_SEQUENCE_STEPS) return;

    llOwnerSay(
        "STEP "
        + (string)(sequenceIndex + 1)
        + " START POS="
        + (string)position
    );
}

debugSequenceStepEnd()
{
    if (!DEBUG_SEQUENCE_STEPS) return;

    llOwnerSay(
        "STEP "
        + (string)(sequenceIndex + 1)
        + " END POS="
        + (string)localPosition(anchorLink)
    );
}

beginSequenceHold(float holdDuration)
{
    elapsed = 0.0;
    duration = holdDuration;

    if (duration < TIMER_STEP)
    {
        duration = TIMER_STEP;
    }

    runPhase = PHASE_SEQUENCE_HOLD;
    playing = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

integer prepareSingleMotion(string normalizedAction)
{
    vector homeAnchor = llList2Vector(homePositions, anchorIndex);
    vector startMarker = localPosition(startMarkerLink);
    vector stopMarker = localPosition(stopMarkerLink);
    vector endMarker = localPosition(endMarkerLink);
    float speed = GO_SPEED;

    motionStart = homeAnchor;
    applyAnchorPosition(motionStart);

    if (normalizedAction == "STOP")
    {
        motionTarget = homeAnchor + (stopMarker - startMarker);
        speed = STOP_SPEED;
    }
    else if (normalizedAction == "CAUTION")
    {
        motionTarget = homeAnchor + (endMarker - startMarker);
        speed = CAUTION_SPEED;
    }
    else if (normalizedAction == "GO")
    {
        motionTarget = homeAnchor + (endMarker - startMarker);
        speed = GO_SPEED;
    }
    else
    {
        return FALSE;
    }

    float distance = llVecDist(motionStart, motionTarget);
    duration = distance / speed;
    if (duration < TIMER_STEP) duration = TIMER_STEP;

    elapsed = 0.0;
    runPhase = PHASE_MOVE;
    playing = TRUE;
    llSetTimerEvent(TIMER_STEP);
    return TRUE;
}

integer prepareSequenceMotion(vector targetAnchor, float speed, string targetName)
{
    vector startAnchor = sequenceStartAnchor();
    vector endAnchor = sequenceEndAnchor();
    vector route = endAnchor - startAnchor;
    float routeLengthSquared = route * route;

    motionStart = localPosition(anchorLink);
    motionTarget = targetAnchor;

    if (routeLengthSquared <= ROUTE_EPSILON)
    {
        llOwnerSay(
            "TRAFFIC VEHICLE STEP "
            + (string)(sequenceIndex + 1)
            + ": rute marker_start ke marker_end memiliki panjang nol. "
            + "Mobil diam di posisi saat ini; sequence tetap lanjut."
        );
        beginSequenceHold(INVALID_ACTION_HOLD);
        return FALSE;
    }

    float currentProgress = progressAlongRoute(motionStart, startAnchor, endAnchor);
    float targetProgress = progressAlongRoute(motionTarget, startAnchor, endAnchor);

    if (currentProgress >= targetProgress - TARGET_EPSILON)
    {
        llOwnerSay(
            "TRAFFIC VEHICLE STEP "
            + (string)(sequenceIndex + 1)
            + ": target "
            + targetName
            + " sudah dicapai atau dilewati. Mobil tetap di posisi saat ini."
        );
        beginSequenceHold(TARGET_REACHED_HOLD);
        return FALSE;
    }

    float distance = llVecDist(motionStart, motionTarget);

    if (distance <= TARGET_EPSILON)
    {
        llOwnerSay(
            "TRAFFIC VEHICLE STEP "
            + (string)(sequenceIndex + 1)
            + ": target "
            + targetName
            + " sudah berada dalam toleransi. Mobil tetap di posisi saat ini."
        );
        beginSequenceHold(TARGET_REACHED_HOLD);
        return FALSE;
    }

    if (speed <= 0.0)
    {
        llOwnerSay(
            "TRAFFIC VEHICLE STEP "
            + (string)(sequenceIndex + 1)
            + ": kecepatan tidak valid. Mobil diam di posisi saat ini; sequence tetap lanjut."
        );
        beginSequenceHold(INVALID_ACTION_HOLD);
        return FALSE;
    }

    duration = distance / speed;
    if (duration < TIMER_STEP) duration = TIMER_STEP;

    elapsed = 0.0;
    runPhase = PHASE_MOVE;
    playing = TRUE;
    llSetTimerEvent(TIMER_STEP);
    return TRUE;
}

startSequenceStep()
{
    if (!sequenceMode || sequenceIndex < 0 || sequenceIndex >= sequenceCount)
    {
        finishAnimation();
        return;
    }

    string color = llList2String(sequenceColors, sequenceIndex);
    string actual = llList2String(sequenceActuals, sequenceIndex);
    string expected = llList2String(sequenceExpecteds, sequenceIndex);
    vector currentAnchor = localPosition(anchorLink);

    nextStopLightPrimed = FALSE;
    llMessageLinked(LINK_SET, MSG_STEP_LIGHT, color, NULL_KEY);
    debugSequenceStepStart(currentAnchor);

    activeAction = normalizeAction(actual);

    llOwnerSay(
        "TRAFFIC RESULT_SEQ STEP "
        + (string)(sequenceIndex + 1)
        + "/"
        + (string)sequenceCount
        + ": warna="
        + color
        + " | actual="
        + actual
        + " | expected="
        + expected
    );

    if (activeAction == "STOP")
    {
        llOwnerSay(
            "TRAFFIC VEHICLE STEP "
            + (string)(sequenceIndex + 1)
            + ": STOP menahan mobil di posisi saat ini."
        );
        beginSequenceHold(STOP_HOLD);
        return;
    }

    if (activeAction == "CAUTION")
    {
        prepareSequenceMotion(sequenceStopAnchor(), CAUTION_SPEED, "marker_stop");
        return;
    }

    if (activeAction == "GO")
    {
        prepareSequenceMotion(sequenceEndAnchor(), GO_SPEED, "marker_end");
        return;
    }

    llOwnerSay(
        "TRAFFIC VEHICLE STEP "
        + (string)(sequenceIndex + 1)
        + ": actual output tidak dikenali. Mobil diam di posisi saat ini; sequence tetap lanjut."
    );
    beginSequenceHold(INVALID_ACTION_HOLD);
}

primeNextStopLightBeforeStop()
{
    if (nextStopLightPrimed) return;
    if (!sequenceMode) return;
    if (activeAction != "CAUTION") return;

    integer nextIndex = sequenceIndex + 1;
    if (nextIndex >= sequenceCount) return;

    string nextAction = normalizeAction(llList2String(sequenceActuals, nextIndex));
    if (nextAction != "STOP") return;

    // Lampu STOP berikutnya dinyalakan sedikit sebelum mobil tiba di
    // marker_stop. Nilai lead dibatasi maksimum seperempat durasi gerak
    // supaya lampu KUNING tetap terlihat selama mobil mendekat.
    float lead = RED_LIGHT_LEAD;
    float proportionalLead = duration * 0.25;

    if (lead > proportionalLead)
    {
        lead = proportionalLead;
    }

    if (lead < TIMER_STEP)
    {
        lead = TIMER_STEP;
    }

    if ((duration - elapsed) > lead) return;

    string nextColor = llList2String(sequenceColors, nextIndex);
    llMessageLinked(LINK_SET, MSG_STEP_LIGHT, nextColor, NULL_KEY);
    nextStopLightPrimed = TRUE;

    if (DEBUG_SEQUENCE_STEPS)
    {
        llOwnerSay(
            "TRAFFIC PRE-SWITCH: lampu step "
            + (string)(nextIndex + 1)
            + " ("
            + nextColor
            + ") aktif sebelum mobil berhenti."
        );
    }
}

continueAfterSequenceStep()
{
    if ((sequenceIndex + 1) >= sequenceCount)
    {
        finishAnimation();
        return;
    }

    // Tidak ada gap antarlampu. Step berikutnya aktif langsung dari
    // posisi akhir step sebelumnya.
    sequenceIndex++;
    startSequenceStep();
}

completeSequenceStep()
{
    debugSequenceStepEnd();
    continueAfterSequenceStep();
}


integer parseSequencePayload(string payload)
{
    list parts = llParseStringKeepNulls(payload, ["|"], []);

    if (llGetListLength(parts) != 4)
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: payload tidak lengkap.");
        return FALSE;
    }

    string attempt = llStringTrim(llList2String(parts, 1), STRING_TRIM);
    integer declaredCount = (integer)llStringTrim(llList2String(parts, 2), STRING_TRIM);

    if (attempt == "")
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: attempt_id kosong.");
        return FALSE;
    }

    if (declaredCount < 1 || declaredCount > MAX_SEQUENCE_STEPS)
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: jumlah_step harus 1 sampai 10.");
        return FALSE;
    }

    list steps = llParseStringKeepNulls(llList2String(parts, 3), [";"], []);

    if (llGetListLength(steps) != declaredCount)
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: jumlah step tidak cocok.");
        return FALSE;
    }

    list colors = [];
    list actuals = [];
    list expecteds = [];
    integer i;

    for (i = 0; i < declaredCount; i++)
    {
        list fields = llParseStringKeepNulls(llList2String(steps, i), ["~"], []);

        if (llGetListLength(fields) != 3)
        {
            llOwnerSay(
                "TRAFFIC VEHICLE RESULT_SEQ DITOLAK: step "
                + (string)(i + 1)
                + " bukan warna~actual~expected."
            );
            return FALSE;
        }

        colors += [llStringTrim(llList2String(fields, 0), STRING_TRIM)];
        actuals += [llStringTrim(llList2String(fields, 1), STRING_TRIM)];
        expecteds += [llStringTrim(llList2String(fields, 2), STRING_TRIM)];
    }

    activeAttempt = attempt;
    sequenceCount = declaredCount;
    sequenceIndex = 0;
    sequenceColors = colors;
    sequenceActuals = actuals;
    sequenceExpecteds = expecteds;
    sequenceMode = TRUE;
    return TRUE;
}

startResult(string payload)
{
    cancelRun(FALSE);

    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT DITOLAK: HOME root belum valid.");
        stopWithoutMoving();
        return;
    }

    if (!loadHome())
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT DITOLAK: jalankan EDIT lalu CALIBRATE.");
        return;
    }

    list parts = llParseStringKeepNulls(payload, ["|"], []);

    if (llGetListLength(parts) < 7)
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT DITOLAK: payload tidak lengkap.");
        return;
    }

    activeAttempt = llList2String(parts, 3);
    activeAction = normalizeAction(llList2String(parts, 5));

    applyAnchorPosition(llList2Vector(homePositions, anchorIndex));

    if (activeAction == "UNKNOWN")
    {
        llOwnerSay(
            "TRAFFIC VEHICLE: actual output tidak dikenali: "
            + llList2String(parts, 5)
            + ". Mobil tetap di marker_start."
        );
        finishAnimation();
        return;
    }

    prepareSingleMotion(activeAction);
}

startResultSequence(string payload)
{
    cancelRun(FALSE);

    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: HOME root belum valid.");
        stopWithoutMoving();
        return;
    }

    if (!loadHome())
    {
        llOwnerSay("TRAFFIC VEHICLE RESULT_SEQ DITOLAK: jalankan EDIT lalu CALIBRATE.");
        return;
    }

    if (!parseSequencePayload(payload))
    {
        cancelRun(FALSE);
        return;
    }

    vector startAnchor = sequenceStartAnchor();
    applyAnchorPosition(startAnchor);

    llOwnerSay(
        "TRAFFIC RESULT_SEQ START FROM CALIBRATED HOME: "
        + (string)startAnchor
    );

    if (DEBUG_SEQUENCE_STEPS)
    {
        llOwnerSay(
            "TRAFFIC RESULT_SEQ TARGETS: marker_start="
            + (string)localPosition(startMarkerLink)
            + " | marker_stop="
            + (string)sequenceStopAnchor()
            + " | marker_end="
            + (string)sequenceEndAnchor()
        );
    }

    startSequenceStep();
}

integer cancelShouldRestore(string reason)
{
    string normalized = llToUpper(llStringTrim(reason, STRING_TRIM));

    if (normalized == "RESULT BARU") return FALSE;
    if (normalized == "RESULT_SEQ BARU") return FALSE;

    // CALIBRATE harus menangkap posisi mobil saat ini.
    // Jangan kembalikan actor ke HOME lama sebelum MSG_CALIBRATE diproses.
    if (normalized == "CALIBRATE") return FALSE;

    return TRUE;
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        playing = FALSE;
        runPhase = PHASE_IDLE;
        clearSequenceData();

        string mode = rootMode();

        if (mode == "RECOVERY")
        {
            stopWithoutMoving();
            llOwnerSay("TRAFFIC VEHICLE RECOVERY: posisi tidak diubah dan pose belum disimpan.");
        }
        else if (mode == "EDIT")
        {
            captureHome();
            llOwnerSay("TRAFFIC VEHICLE AUTO-CALIBRATE: Reset Scripts saat EDIT.");
        }
        else
        {
            resetActor();
        }
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_CANCEL)
        {
            cancelRun(cancelShouldRestore(message));
        }
        else if (number == MSG_CALIBRATE)
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
        else if (number == MSG_RESULT)
        {
            startResult(message);
        }
        else if (number == MSG_RESULT_SEQ)
        {
            startResultSequence(message);
        }
    }

    timer()
    {
        if (!playing || !ready)
        {
            llSetTimerEvent(0.0);
            return;
        }

        elapsed += TIMER_STEP;

        if (runPhase == PHASE_MOVE)
        {
            if (sequenceMode)
            {
                primeNextStopLightBeforeStop();
            }

            float progress = elapsed / duration;
            if (progress > 1.0) progress = 1.0;

            float eased = smoothStep(progress);
            vector position = motionStart + ((motionTarget - motionStart) * eased);
            applyAnchorPosition(position);

            if (progress >= 1.0)
            {
                if (sequenceMode)
                {
                    completeSequenceStep();
                }
                else
                {
                    finishAnimation();
                }
            }
        }
        else if (runPhase == PHASE_SEQUENCE_HOLD)
        {
            if (elapsed >= duration)
            {
                completeSequenceStep();
            }
        }
        else
        {
            finishAnimation();
        }
    }

    changed(integer change)
    {
        if (change & CHANGED_OWNER)
        {
            llResetScript();
        }
    }
}
