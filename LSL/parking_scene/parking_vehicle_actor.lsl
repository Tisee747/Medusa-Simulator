// Parking vehicle actor: animate validated vehicle movements and visibility.
integer MSG_EDIT = 9401;
integer MSG_CALIBRATE = 9402;
integer MSG_SHOW = 9403;
integer MSG_RESET = 9404;
integer MSG_HIDE = 9405;
integer MSG_VEHICLE_ACTION = 9410;
integer MSG_VEHICLE_DONE = 9411;

string STATE_VERSION = "PARKING_V21";
float TIMER_STEP = 0.04;
float APPROACH_SPEED = 4.8;
float PASS_SPEED = 7.5;
float OFFSTAGE_DEPTH = 25.0;
integer BATCH_SIZE = 8;

list motorLinks = [];
list carLinks = [];
list truckLinks = [];
integer motorAnchor = 0;
integer carAnchor = 0;
integer truckAnchor = 0;

string activeVehicle = "";
list activeLinks = [];
list activeHomePositions = [];
list activeHomeRotations = [];
integer activeAnchorIndex = -1;
float currentDistance = 0.0;
float targetDistance = 0.0;
float moveStartDistance = 0.0;
float moveElapsed = 0.0;
float moveDuration = 0.0;
string activeAction = "";
integer moving = FALSE;
integer ready = FALSE;
integer activeVisible = FALSE;
string activeDirection = "EXIT";

// Layout PARKING aktual:
// vehicle_start = kanan/dalam parkir
// vehicle_end   = kiri/luar parkir
vector routeStartPosition = ZERO_VECTOR;
vector routeEndPosition = ZERO_VECTOR;
vector routeDirection = <-1.0, 0.0, 0.0>;
float routeLength = 8.0;
float barrierDistance = 4.0;

string lower(string value)
{
    return llToLower(llStringTrim(value, STRING_TRIM));
}

string upper(string value)
{
    return llToUpper(llStringTrim(value, STRING_TRIM));
}

integer startsWith(string value, string prefix)
{
    return llSubStringIndex(value, prefix) == 0;
}

string rootMode()
{
    list fields = llParseStringKeepNulls(llGetObjectDesc(), ["|"], []);

    if (llGetListLength(fields) < 5) return "RECOVERY";
    if (upper(llList2String(fields, 0)) != "HOME") return "RECOVERY";
    if (upper(llList2String(fields, 1)) != STATE_VERSION) return "RECOVERY";

    return upper(llList2String(fields, 4));
}

integer findExact(string target)
{
    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        if (lower(llGetLinkName(link)) == lower(target)) return link;
    }

    return 0;
}

integer isMotorName(string name)
{
    return (
        name == "vehicle_motor"
        || name == "motor"
        || startsWith(name, "vehicle_motor#")
        || startsWith(name, "vehicle_motor__#")
        || startsWith(name, "motor#")
        || startsWith(name, "motor__#")
    );
}

integer isCarName(string name)
{
    return (
        name == "vehicle_car"
        || name == "car"
        || startsWith(name, "vehicle_car#")
        || startsWith(name, "vehicle_car__#")
        || startsWith(name, "car#")
        || startsWith(name, "car__#")
    );
}

integer isTruckName(string name)
{
    return (
        name == "vehicle_truck"
        || name == "truck"
        || startsWith(name, "vehicle_truck#")
        || startsWith(name, "vehicle_truck__#")
        || startsWith(name, "truck#")
        || startsWith(name, "truck__#")
    );
}

integer discoverVehicles()
{
    motorLinks = [];
    carLinks = [];
    truckLinks = [];
    motorAnchor = 0;
    carAnchor = 0;
    truckAnchor = 0;

    integer count = llGetNumberOfPrims();
    integer link;

    for (link = 1; link <= count; link++)
    {
        string name = lower(llGetLinkName(link));

        if (isMotorName(name))
        {
            motorLinks += [link];
            if (name == "vehicle_motor" || name == "motor") motorAnchor = link;
        }
        else if (isCarName(name))
        {
            carLinks += [link];
            if (name == "vehicle_car" || name == "car") carAnchor = link;
        }
        else if (isTruckName(name))
        {
            truckLinks += [link];
            if (name == "vehicle_truck" || name == "truck") truckAnchor = link;
        }
    }

    integer valid = TRUE;

    if (!llGetListLength(motorLinks) || !motorAnchor)
    {
        llOwnerSay("PARKING VEHICLE ERROR: grup/anchor MOTOR tidak ditemukan.");
        valid = FALSE;
    }

    if (!llGetListLength(carLinks) || !carAnchor)
    {
        llOwnerSay("PARKING VEHICLE ERROR: grup/anchor MOBIL tidak ditemukan.");
        valid = FALSE;
    }

    if (!llGetListLength(truckLinks) || !truckAnchor)
    {
        llOwnerSay("PARKING VEHICLE ERROR: grup/anchor TRUK tidak ditemukan.");
        valid = FALSE;
    }

    return valid;
}

list linksFor(string vehicle)
{
    vehicle = upper(vehicle);
    if (vehicle == "MOTOR") return motorLinks;
    if (vehicle == "MOBIL") return carLinks;
    if (vehicle == "TRUK") return truckLinks;
    return [];
}

integer anchorFor(string vehicle)
{
    vehicle = upper(vehicle);
    if (vehicle == "MOTOR") return motorAnchor;
    if (vehicle == "MOBIL") return carAnchor;
    if (vehicle == "TRUK") return truckAnchor;
    return 0;
}

float clearanceFor(string vehicle)
{
    vehicle = upper(vehicle);
    if (vehicle == "MOTOR") return 1.25;
    if (vehicle == "MOBIL") return 2.10;
    if (vehicle == "TRUK") return 3.00;
    return 2.00;
}

integer validHomeDescription(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);

    return (
        llGetListLength(fields) >= 4
        && upper(llList2String(fields, 0)) == "HOME"
        && upper(llList2String(fields, 1)) == STATE_VERSION
    );
}

vector homePositionFor(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);
    return (vector)llList2String(fields, 2);
}

rotation homeRotationFor(integer link)
{
    string description = llList2String(llGetLinkPrimitiveParams(link, [PRIM_DESC]), 0);
    list fields = llParseStringKeepNulls(description, ["|"], []);
    return (rotation)llList2String(fields, 3);
}

integer captureGroup(list links)
{
    integer count = llGetListLength(links);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(links, i);
        list data = llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
        vector position = llList2Vector(data, 0);
        rotation rot = llList2Rot(data, 1);

        llSetLinkPrimitiveParamsFast(
            link,
            [PRIM_DESC, "HOME|" + STATE_VERSION + "|" + (string)position + "|" + (string)rot]
        );
    }

    return count;
}

captureAll()
{
    moving = FALSE;
    activeVisible = FALSE;
    llSetTimerEvent(0.0);

    if (!discoverVehicles())
    {
        ready = FALSE;
        return;
    }

    integer motorCount = captureGroup(motorLinks);
    integer carCount = captureGroup(carLinks);
    integer truckCount = captureGroup(truckLinks);
    ready = TRUE;

    llOwnerSay(
        "PARKING VEHICLES CALIBRATED: MOTOR=" + (string)motorCount
        + ", MOBIL=" + (string)carCount
        + ", TRUK=" + (string)truckCount + "."
    );
}

integer groupHasHome(list links)
{
    integer count = llGetListLength(links);
    integer i;

    if (count == 0) return FALSE;

    for (i = 0; i < count; i++)
    {
        if (!validHomeDescription(llList2Integer(links, i))) return FALSE;
    }

    return TRUE;
}

integer loadAllHomes()
{
    if (!discoverVehicles()) return FALSE;

    if (!groupHasHome(motorLinks) || !groupHasHome(carLinks) || !groupHasHome(truckLinks))
    {
        llOwnerSay("PARKING VEHICLE HOME BELUM LENGKAP: jalankan EDIT lalu CALIBRATE.");
        return FALSE;
    }

    return TRUE;
}

applyStoredGroup(list links, vector offset)
{
    integer count = llGetListLength(links);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(links, i);

        if (validHomeDescription(link))
        {
            rules += [
                PRIM_LINK_TARGET, link,
                PRIM_POS_LOCAL, homePositionFor(link) + offset,
                PRIM_ROT_LOCAL, homeRotationFor(link)
            ];
            batchCount++;

            if (batchCount >= BATCH_SIZE)
            {
                llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
                rules = [];
                batchCount = 0;
            }
        }
    }

    if (llGetListLength(rules))
    {
        llSetLinkPrimitiveParamsFast(LINK_ROOT, rules);
    }
}

hideGroup(list links)
{
    applyStoredGroup(links, <0.0, 0.0, -OFFSTAGE_DEPTH>);
}

hideAll()
{
    moving = FALSE;
    activeVisible = FALSE;
    llSetTimerEvent(0.0);

    if (rootMode() == "RECOVERY")
    {
        discoverVehicles();
        ready = FALSE;
        return;
    }

    if (!loadAllHomes())
    {
        ready = FALSE;
        return;
    }

    hideGroup(motorLinks);
    hideGroup(carLinks);
    hideGroup(truckLinks);
    ready = TRUE;
}

showAllAtHome()
{
    moving = FALSE;
    activeVisible = FALSE;
    llSetTimerEvent(0.0);

    if (rootMode() == "RECOVERY")
    {
        discoverVehicles();
        ready = FALSE;
        return;
    }

    if (!loadAllHomes())
    {
        ready = FALSE;
        return;
    }

    applyStoredGroup(motorLinks, ZERO_VECTOR);
    applyStoredGroup(carLinks, ZERO_VECTOR);
    applyStoredGroup(truckLinks, ZERO_VECTOR);
    ready = TRUE;
}

integer loadRoute()
{
    integer startLink = findExact("vehicle_start");
    integer endLink = findExact("vehicle_end");
    integer barrierLink = findExact("barrier_arm");

    if (!startLink || !endLink)
    {
        llOwnerSay("PARKING ROUTE ERROR: vehicle_start atau vehicle_end tidak ditemukan.");
        return FALSE;
    }

    vector startPosition = llList2Vector(llGetLinkPrimitiveParams(startLink, [PRIM_POS_LOCAL]), 0);
    vector endPosition = llList2Vector(llGetLinkPrimitiveParams(endLink, [PRIM_POS_LOCAL]), 0);
    routeStartPosition = startPosition;
    routeEndPosition = endPosition;
    vector horizontal = endPosition - startPosition;
    horizontal.z = 0.0;

    routeLength = llVecMag(horizontal);
    if (routeLength < 1.0)
    {
        llOwnerSay("PARKING ROUTE ERROR: jarak marker start-end terlalu pendek.");
        return FALSE;
    }

    routeDirection = llVecNorm(horizontal);

    if (barrierLink)
    {
        vector barrierPosition = llList2Vector(llGetLinkPrimitiveParams(barrierLink, [PRIM_POS_LOCAL]), 0);
        vector fromStart = barrierPosition - startPosition;
        fromStart.z = 0.0;
        barrierDistance = fromStart * routeDirection;
    }
    else
    {
        barrierDistance = routeLength * 0.5;
        llOwnerSay("PARKING ROUTE WARNING: barrier_arm tidak ditemukan; titik stop memakai tengah rute.");
    }

    if (barrierDistance < 1.0) barrierDistance = routeLength * 0.5;
    if (barrierDistance > routeLength - 1.0) barrierDistance = routeLength * 0.5;

    return TRUE;
}

integer loadActive(string vehicle)
{
    activeVehicle = upper(vehicle);
    activeLinks = linksFor(activeVehicle);
    integer anchor = anchorFor(activeVehicle);
    activeAnchorIndex = llListFindList(activeLinks, [anchor]);
    activeHomePositions = [];
    activeHomeRotations = [];

    if (!llGetListLength(activeLinks) || activeAnchorIndex < 0)
    {
        llOwnerSay("PARKING VEHICLE ERROR: actor aktif tidak ditemukan: " + activeVehicle);
        return FALSE;
    }

    integer count = llGetListLength(activeLinks);
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(activeLinks, i);

        if (!validHomeDescription(link))
        {
            llOwnerSay("PARKING " + activeVehicle + " HOME BELUM LENGKAP: " + llGetLinkName(link));
            return FALSE;
        }

        activeHomePositions += [homePositionFor(link)];
        activeHomeRotations += [homeRotationFor(link)];
    }

    return TRUE;
}

applyActiveDistance(float distance)
{
    if (!ready || activeAnchorIndex < 0) return;

    // Pose HOME kendaraan menghadap arah EXIT: kanan ke kiri.
    // ENTER memakai arah kebalikannya.
    rotation directionRotation = ZERO_ROTATION;
    if (activeDirection == "ENTER")
    {
        directionRotation = llEuler2Rot(<0.0, 0.0, PI>);
    }

    vector homePivot = llList2Vector(activeHomePositions, activeAnchorIndex);
    vector targetPivot = routeStartPosition + (routeDirection * distance);

    // Marker hanya menentukan jalur X/Y. Tinggi kendaraan tetap dari HOME.
    targetPivot.z = homePivot.z;

    integer count = llGetListLength(activeLinks);
    list rules = [];
    integer batchCount = 0;
    integer i;

    for (i = 0; i < count; i++)
    {
        integer link = llList2Integer(activeLinks, i);
        vector basePosition = llList2Vector(activeHomePositions, i);
        rotation baseRotation = llList2Rot(activeHomeRotations, i);
        vector offset = basePosition - homePivot;
        vector newPosition = targetPivot + (offset * directionRotation);
        rotation newRotation = baseRotation * directionRotation;

        rules += [
            PRIM_LINK_TARGET, link,
            PRIM_POS_LOCAL, newPosition,
            PRIM_ROT_LOCAL, newRotation
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

sendDone(string action)
{
    llMessageLinked(LINK_SET, MSG_VEHICLE_DONE, action + "|" + activeVehicle, NULL_KEY);
}

integer placeVehicle(string vehicle, string side)
{
    moving = FALSE;
    llSetTimerEvent(0.0);

    if (!loadAllHomes() || !loadRoute() || !loadActive(vehicle))
    {
        ready = FALSE;
        return FALSE;
    }

    hideGroup(motorLinks);
    hideGroup(carLinks);
    hideGroup(truckLinks);

    // START adalah kanan/dalam dan merupakan titik awal EXIT.
    currentDistance = 0.0;
    activeDirection = "EXIT";

    // END adalah kiri/luar dan merupakan titik awal ENTER.
    if (upper(side) == "END")
    {
        currentDistance = routeLength;
        activeDirection = "ENTER";
    }

    ready = TRUE;
    applyActiveDistance(currentDistance);
    activeVisible = TRUE;
    return TRUE;
}

showVehicle(string vehicle, string side)
{
    if (placeVehicle(vehicle, side)) sendDone("SHOW");
}

startMove(string action, float destination, float speed)
{
    if (!activeVisible)
    {
        string side = "START";
        if (activeDirection == "ENTER") side = "END";
        placeVehicle(activeVehicle, side);
    }

    if (!ready || !activeVisible) return;

    // Pastikan arah badan sesuai arah perjalanan sebelum mulai bergerak.
    applyActiveDistance(currentDistance);

    moveStartDistance = currentDistance;
    targetDistance = destination;
    activeAction = action;
    moveElapsed = 0.0;

    float distance = llFabs(targetDistance - moveStartDistance);
    if (distance < 0.01)
    {
        currentDistance = targetDistance;
        applyActiveDistance(currentDistance);
        sendDone(activeAction);
        return;
    }

    moveDuration = distance / speed;
    if (moveDuration < TIMER_STEP) moveDuration = TIMER_STEP;

    moving = TRUE;
    llSetTimerEvent(TIMER_STEP);
}

approach(string direction)
{
    direction = upper(direction);
    if (direction != "ENTER") direction = "EXIT";
    activeDirection = direction;

    if (!activeVisible)
    {
        string side = "START";
        if (activeDirection == "ENTER") side = "END";
        placeVehicle(activeVehicle, side);
    }

    float clearance = clearanceFor(activeVehicle);
    // EXIT bergerak dari distance 0 menuju routeLength.
    // Berhenti di sisi kanan/dalam sebelum barrier.
    float destination = barrierDistance - clearance;

    // ENTER bergerak dari routeLength menuju 0.
    // Berhenti di sisi kiri/luar sebelum barrier.
    if (activeDirection == "ENTER")
    {
        destination = barrierDistance + clearance;
    }

    if (destination < 0.0) destination = 0.0;
    if (destination > routeLength) destination = routeLength;

    startMove("APPROACH", destination, APPROACH_SPEED);
}

enterVehicle()
{
    activeDirection = "ENTER";
    startMove("ENTER", 0.0, PASS_SPEED);
}

exitVehicle()
{
    activeDirection = "EXIT";
    startMove("EXIT", routeLength, PASS_SPEED);
}

hideActive()
{
    moving = FALSE;
    llSetTimerEvent(0.0);

    if (llGetListLength(activeLinks)) hideGroup(activeLinks);

    activeVisible = FALSE;
    sendDone("HIDE");
}

resetActive()
{
    moving = FALSE;
    llSetTimerEvent(0.0);

    if (!loadAllHomes() || !loadRoute() || !loadActive(activeVehicle))
    {
        ready = FALSE;
        return;
    }

    hideGroup(motorLinks);
    hideGroup(carLinks);
    hideGroup(truckLinks);
    activeDirection = "EXIT";
    currentDistance = 0.0;
    applyActiveDistance(currentDistance);
    activeVisible = TRUE;
    ready = TRUE;
    sendDone("RESET");
}

handleAction(string message)
{
    list fields = llParseStringKeepNulls(message, ["|"], []);
    string action = upper(llList2String(fields, 0));
    string vehicle = upper(llList2String(fields, 1));
    string parameter = upper(llList2String(fields, 2));

    if (rootMode() == "RECOVERY")
    {
        llOwnerSay("PARKING VEHICLE ACTION DITOLAK: HOME belum valid.");
        return;
    }

    if (vehicle != activeVehicle || !llGetListLength(activeLinks))
    {
        if (!loadAllHomes() || !loadRoute() || !loadActive(vehicle))
        {
            ready = FALSE;
            return;
        }
        ready = TRUE;
    }

    if (action == "SHOW") showVehicle(vehicle, parameter);
    else if (action == "APPROACH") approach(parameter);
    else if (action == "STOP") sendDone("STOP");
    else if (action == "ENTER") enterVehicle();
    else if (action == "EXIT") exitVehicle();
    else if (action == "HIDE") hideActive();
    else if (action == "RESET") resetActive();
}

default
{
    state_entry()
    {
        llSetTimerEvent(0.0);
        string currentMode = rootMode();

        if (currentMode == "RECOVERY")
        {
            moving = FALSE;
            ready = FALSE;
            discoverVehicles();
            llOwnerSay("PARKING VEHICLE RECOVERY V2.1: posisi tidak diubah dan HOME belum disimpan.");
        }
        else if (currentMode == "EDIT")
        {
            captureAll();
            llOwnerSay("PARKING VEHICLE AUTO-CALIBRATE: Reset Scripts saat EDIT.");
        }
        else
        {
            hideAll();
        }
    }

    link_message(integer sender, integer number, string message, key id)
    {
        if (number == MSG_CALIBRATE)
        {
            captureAll();
        }
        else if (number == MSG_EDIT)
        {
            if (rootMode() == "RECOVERY")
            {
                moving = FALSE;
                llSetTimerEvent(0.0);
                discoverVehicles();
            }
            else
            {
                showAllAtHome();
            }
        }
        else if (number == MSG_SHOW || number == MSG_RESET || number == MSG_HIDE)
        {
            hideAll();
        }
        else if (number == MSG_VEHICLE_ACTION)
        {
            handleAction(message);
        }
    }

    timer()
    {
        if (!moving || !ready || !activeVisible) return;

        moveElapsed += TIMER_STEP;
        float progress = moveElapsed / moveDuration;

        if (progress >= 1.0)
        {
            progress = 1.0;
            moving = FALSE;
        }

        float eased = progress * progress * (3.0 - 2.0 * progress);
        currentDistance = moveStartDistance + (targetDistance - moveStartDistance) * eased;
        applyActiveDistance(currentDistance);

        if (!moving)
        {
            llSetTimerEvent(0.0);
            currentDistance = targetDistance;
            sendDone(activeAction);
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
