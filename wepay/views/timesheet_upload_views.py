from datetime import datetime, timedelta, date
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import connection, transaction
from wepay.models import TimesheetRecord, Employee, GeneralLog, OBRequest, LastPayRecord
from wepay.serializers import TimesheetRecordSerializer


def generate_timesheet_id():
    # Gumagawa ng unique Timesheet ID base sa current month/year
    # Halimbawa: TS0426-0001
    year = datetime.now().year
    month = datetime.now().month
    year_short = year % 100

    # Hanapin ang pinakamataas na existing sequence para sa buwan na ito
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MAX(CAST(SUBSTRING(timesheet_id, 8, 4) AS UNSIGNED))
            FROM timesheet_uploads
            WHERE SUBSTRING(timesheet_id, 3, 4) = %s
            """,
            [f"{month:02d}{year_short:02d}"],
        )
        result = cursor.fetchone()
        max_sequence = result[0] if result[0] else 0

    # I-increment ng 1 yung sequence
    sequence = str(max_sequence + 1).zfill(4)
    return f"TS{month:02d}{year_short:02d}-{sequence}"


def get_employee_data(emp_id):
    # Kunin ang employee details mula sa employee_record at employee tables
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONCAT(emp.first_name, ' ', emp.last_name) as emp_name,
                   e.position, e.dept_id, e.emp_status, emp.biometric_id
            FROM employee_record e
            LEFT JOIN employee emp ON e.emp_id = emp.emp_id
            WHERE e.emp_id = %s
            """,
            [emp_id],
        )
        return cursor.fetchone()


def get_employee_schedule(emp_id, tran_date):
    """
    Kunin ang schedule ng employee para sa specific na date.
    Una, tingnan ang employee_schedule (specific date).
    Kung wala, tingnan ang employee_schedule_default (weekly default).
    Returns: (time_in, time_out, rest_day) or None
    """
    day_of_week = tran_date.isoweekday()  # 1=Monday, 7=Sunday

    with connection.cursor() as cursor:
        # Tingnan muna ang specific date schedule
        cursor.execute(
            """
            SELECT time_in, time_out, rest_day
            FROM employee_schedule
            WHERE emp_id = %s AND tran_date = %s
            """,
            [emp_id, tran_date],
        )
        result = cursor.fetchone()

        if result:
            return result

        # Kung wala, tingnan ang default weekly schedule
        cursor.execute(
            """
            SELECT time_in, time_out, rest_day
            FROM employee_schedule_default
            WHERE emp_id = %s AND tran_day = %s
            """,
            [emp_id, day_of_week],
        )
        return cursor.fetchone()


def get_employee_compressed_status(emp_id):
    # Tingnan kung compressed employee ba siya
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT is_compressed
            FROM employee
            WHERE emp_id = %s
            """,
            [emp_id],
        )
        result = cursor.fetchone()
        return result and result[0] == "Y"


def get_holidays_for_period(start_date, end_date):
    """
    Kunin lahat ng holidays mula sa holiday_calendar para sa given date range.
    Returns: set ng date objects na representing holidays
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT month_no, day_no, year_no
            FROM holiday_calendar
            WHERE active = 'Y'
            AND (year_no = 0 OR year_no = %s)
            """,
            [end_date.year],
        )
        holiday_rows = cursor.fetchall()

    holiday_dates = set()
    for month, day, year in holiday_rows:
        try:
            # year_no = 0 means recurring every year
            h_date = (
                date(end_date.year, month, day) if year == 0
                else date(year, month, day)
            )
            # Isama lang ang holidays na nasa loob ng date range
            if start_date <= h_date <= end_date:
                holiday_dates.add(h_date)
        except ValueError:
            pass

    return holiday_dates


def get_merged_attendance(emp_id, biometric_id, dates):
    """
    I-merge ang biometric data at approved OB requests para sa complete attendance.
    Priority rules:
    - May bio time_in at time_out + OB: sundin ang bio, i-note lang ang OB
    - May bio time_in lang + OB time_in na mas maaga: gamitin OB time_in
    - Walang bio data: gamitin lahat ng OB data
    """
    merged_attendance = {}

    # Kunin lahat ng approved OB requests para sa mga dates na ito
    ob_requests = OBRequest.objects.filter(
        emp_id=emp_id,
        sched_date__in=dates,
        status="AP"  # Approved lang
    ).order_by("sched_date")

    # I-organize ang OB requests by date para madaling lookup
    ob_dict = {}
    for ob in ob_requests:
        ob_dict[ob.sched_date] = {
            "time_in": ob.time_in,
            "time_out": ob.time_out.time() if ob.time_out else None,
            "remarks": ob.remarks or "OFFICIAL BUSINESS",
        }

    # I-process ang bawat date
    for tran_date in dates:
        with connection.cursor() as cursor:
            # Kunin lahat ng punch records para sa date na ito, sorted by time
            cursor.execute(
                """
                SELECT tran_time
                FROM lp_inout
                WHERE biometric_id = %s AND tran_date = %s
                ORDER BY tran_time
                """,
                [biometric_id, tran_date],
            )
            time_records = cursor.fetchall()

        # Default na empty attendance data
        merged_data = {
            "date": tran_date,
            "time_in": None,
            "time_out": None,
            "remarks": None,
            "source": "biometric",
        }

        # I-process ang biometric punches — first punch = time_in, last punch = time_out
        if time_records:
            merged_data["time_in"] = time_records[0][0]
            merged_data["time_out"] = time_records[-1][0] if len(time_records) > 1 else None

        # I-check kung may approved OB request para sa date na ito
        if tran_date in ob_dict:
            ob_data = ob_dict[tran_date]

            if time_records and merged_data["time_in"] and merged_data["time_out"]:
                # May kumpleto na bio data — sundin bio, i-note lang ang OB
                merged_data["remarks"] = f"Biometric (OB overridden): {ob_data['remarks']}"
                merged_data["source"] = "bio_priority"

            elif time_records and merged_data["time_in"] and ob_data["time_in"]:
                # May bio time_in pero walang time_out — i-compare ang OB time_in
                bio_time_in = datetime.strptime(merged_data["time_in"].strftime("%H:%M:%S"), "%H:%M:%S")
                ob_time_in = datetime.strptime(ob_data["time_in"].strftime("%H:%M:%S"), "%H:%M:%S")

                if ob_time_in < bio_time_in:
                    # OB time_in mas maaga — gamitin OB time_in + bio time_out
                    merged_data["time_in"] = ob_data["time_in"]
                    merged_data["remarks"] = f"OB time_in + Bio time_out: {ob_data['remarks']}"
                    merged_data["source"] = "ob_early_in"
                else:
                    # Bio time_in mas maaga — sundin bio
                    merged_data["remarks"] = f"Biometric (OB overridden): {ob_data['remarks']}"
                    merged_data["source"] = "bio_priority"

            else:
                # Walang bio data — gamitin OB para punan ang gaps
                if not merged_data["time_in"] and ob_data["time_in"]:
                    merged_data["time_in"] = ob_data["time_in"]
                    merged_data["source"] = "ob_merged"

                if not merged_data["time_out"] and ob_data["time_out"]:
                    merged_data["time_out"] = ob_data["time_out"]
                    merged_data["source"] = "ob_merged"

                if not time_records:
                    # Walang bio talaga — OB lang ang data
                    merged_data["time_in"] = ob_data["time_in"]
                    merged_data["time_out"] = ob_data["time_out"]
                    merged_data["remarks"] = ob_data["remarks"]
                    merged_data["source"] = "ob_only"
                elif merged_data["source"] == "ob_merged":
                    merged_data["remarks"] = f"Biometric + OB: {ob_data['remarks']}"

        merged_attendance[tran_date] = merged_data

    return merged_attendance


@api_view(["POST"])
def upload_timesheet(request):
    # I-upload ang txt file at i-parse papunta sa database
    try:
        with transaction.atomic():
            # Dapat may file na naka-attach
            if "file" not in request.FILES:
                return Response(
                    {"result": "error", "message": "No file provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Dapat may employee ID
            if "emp_id" not in request.POST:
                return Response(
                    {"result": "error", "message": "Employee ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file = request.FILES["file"]
            emp_id = request.POST["emp_id"]
            active_user = request.data.get("performed_by", "system")

            # Txt files lang ang tinatanggap
            if not file.name.lower().endswith(".txt"):
                return Response(
                    {"result": "error", "message": "Only .txt files are allowed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Kunin ang employee details
            employee_data = get_employee_data(emp_id)
            if not employee_data:
                return Response(
                    {"result": "error", "message": f"Employee with ID {emp_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            emp_name, position, department_id, emp_status, biometric_id = employee_data

            # Kelangan ng biometric ID para ma-process ang timesheet
            if not biometric_id:
                return Response(
                    {"result": "error", "message": f"Employee {emp_id} has no biometric ID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Burahin muna ang existing records bago mag-upload ng bago
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM lp_inout WHERE biometric_id = %s", [biometric_id])
                cursor.execute("DELETE FROM lp_timesheet WHERE emp_id = %s", [emp_id])
                cursor.execute("DELETE FROM timesheet_uploads WHERE emp_id = %s", [emp_id])

            # Basahin ang file — try UTF-8 muna, may fallback sa ibang encodings
            try:
                content = file.read().decode("utf-8").strip()
            except UnicodeDecodeError:
                file.seek(0)
                try:
                    content = file.read().decode("latin-1").strip()
                except UnicodeDecodeError:
                    file.seek(0)
                    content = file.read().decode("cp1252").strip()

            lines = content.split("\n")

            if not lines:
                return Response(
                    {"result": "error", "message": "File is empty"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            timesheet_id = generate_timesheet_id()
            total_days_worked = 0.0
            valid_entries = 0
            biometric_dates = set()

            # --- PASS 1: I-parse ang dates at i-check ang collision sa payroll ---
            for line in lines:
                line = line.strip()

                # Laktawan ang blank lines at header
                if not line or line.startswith("biometric_id"):
                    continue

                try:
                    if "\t" not in line:
                        continue

                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue

                    file_biometric_id = parts[0].strip()
                    date_time_str = parts[1].strip()

                    # Itong employee lang ang i-process, hindi yung iba
                    if file_biometric_id != str(biometric_id):
                        continue

                    parsed_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
                    biometric_dates.add(parsed_datetime.date())
                    valid_entries += 1

                except (ValueError, IndexError):
                    continue

            # I-check kung may conflict sa existing payroll periods
            if biometric_dates:
                with connection.cursor() as cursor:
                    for parsed_date in sorted(biometric_dates):
                        cursor.execute(
                            """
                            SELECT DISTINCT b.period_start_date, b.period_end_date
                            FROM payroll_data a
                            LEFT JOIN payroll_header b ON a.payroll_id = b.id
                            WHERE a.emp_id = %s
                            AND %s BETWEEN b.period_start_date AND b.period_end_date
                            """,
                            [emp_id, parsed_date],
                        )
                        collision = cursor.fetchone()
                        if collision:
                            period_start, period_end = collision
                            return Response(
                                {
                                    "result": "error",
                                    "message": (
                                        f"Cannot upload: Date {parsed_date} falls within existing "
                                        f"payroll period ({period_start} to {period_end}) for employee {emp_id}"
                                    ),
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

            # --- PASS 2: I-insert na ang records sa lp_inout ---
            for line in lines:
                line = line.strip()

                if not line or line.startswith("biometric_id"):
                    continue

                try:
                    if "\t" not in line:
                        continue

                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue

                    file_biometric_id = parts[0].strip()
                    date_time_str = parts[1].strip()

                    if file_biometric_id != str(biometric_id):
                        continue

                    parsed_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
                    parsed_date = parsed_datetime.date()
                    time_only = parsed_datetime.time()

                    with connection.cursor() as inout_cursor:
                        inout_cursor.execute(
                            """
                            INSERT INTO lp_inout (biometric_id, tran_date, tran_time)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE tran_time = VALUES(tran_time)
                            """,
                            [file_biometric_id, parsed_date, time_only.strftime("%H:%M:%S")],
                        )

                except (ValueError, IndexError):
                    continue

            # Isama rin ang dates mula sa approved OB requests
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT sched_date
                    FROM ob_request
                    WHERE emp_id = %s AND status = 'AP'
                    """,
                    [emp_id],
                )
                ob_dates = set(row[0] for row in cursor.fetchall())

            # Pagsamahin ang bio dates at OB dates
            all_dates = biometric_dates | ob_dates

            # Kunin ang holidays — mag-add ng buffer para sa week-level checks ng compressed employees
            if all_dates:
                min_date = min(all_dates) - timedelta(days=6)
                max_date = max(all_dates) + timedelta(days=6)
                holiday_dates = get_holidays_for_period(min_date, max_date)
            else:
                holiday_dates = set()

            # I-merge ang biometric at OB attendance data
            merged_attendance = get_merged_attendance(emp_id, biometric_id, sorted(all_dates))

            # Kunin ang compressed status — once lang, gagamitin sa buong loop
            is_compressed_employee = get_employee_compressed_status(emp_id)
            is_compressed = "Y" if is_compressed_employee else "N"

            # --- MAIN LOOP: I-compute at i-save ang lp_timesheet records ---
            for parsed_date, attendance_data in merged_attendance.items():
                try:
                    time_in = attendance_data["time_in"]
                    time_out = attendance_data["time_out"]

                    # Wala talagang data — laktawan
                    if not time_in and not time_out:
                        continue

                    time_in_str = time_in.strftime("%H:%M:%S") if time_in else None
                    time_out_str = time_out.strftime("%H:%M:%S") if time_out else None

                    # Kunin ang schedule ng employee para sa date na ito
                    schedule = get_employee_schedule(emp_id, parsed_date)

                    # Para sa compressed employees, i-compute ang week info — gagamitin sa
                    # schedule override at day_max calculation para hindi mag-duplicate
                    if is_compressed_employee:
                        day_of_week = parsed_date.isoweekday()
                        week_start = parsed_date - timedelta(days=day_of_week - 1)
                        week_end = week_start + timedelta(days=6)
                        holidays_in_week = any(week_start <= h <= week_end for h in holiday_dates)

                        # Kung may holiday sa linggo, i-override ang schedule to 08:00-17:00
                        if holidays_in_week and schedule and schedule[0] and schedule[1]:
                            schedule = (
                                datetime.strptime("08:00:00", "%H:%M:%S").time(),
                                datetime.strptime("17:00:00", "%H:%M:%S").time(),
                                schedule[2],  # Panatilihin ang rest_day
                            )
                    else:
                        day_of_week = parsed_date.isoweekday()
                        holidays_in_week = False  # Hindi relevant para sa non-compressed

                    # I-check kung makeup Saturday ba ito (compressed na may holiday sa Mon-Fri)
                    is_makeup_saturday = False
                    if is_compressed_employee and day_of_week == 6:
                        week_start_mon = parsed_date - timedelta(days=5)  # Monday
                        week_end_fri = parsed_date - timedelta(days=1)    # Friday
                        if get_holidays_for_period(week_start_mon, week_end_fri):
                            is_makeup_saturday = True
                            # Makeup Saturday — gamitin ang standard 08:00-17:00
                            schedule = (
                                datetime.strptime("08:00:00", "%H:%M:%S").time(),
                                datetime.strptime("17:00:00", "%H:%M:%S").time(),
                                "N",
                            )

                    # Kung walang schedule, laktawan — maliban kung makeup Saturday
                    if not schedule or not schedule[0] or not schedule[1]:
                        if not is_makeup_saturday:
                            continue
                        # Para sa makeup Saturday na walang schedule — borrow ng weekday schedule
                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                SELECT time_in, time_out, rest_day
                                FROM employee_schedule_default
                                WHERE emp_id = %s AND rest_day = 'N'
                                LIMIT 1
                                """,
                                [emp_id],
                            )
                            weekday_sched = cursor.fetchone()
                        if not weekday_sched or not weekday_sched[0] or not weekday_sched[1]:
                            continue
                        sched_time_in = weekday_sched[0]
                        sched_time_out = weekday_sched[1]
                        rest_day = "N"
                    else:
                        sched_time_in, sched_time_out, rest_day = schedule[0], schedule[1], schedule[2]

                    # Para sa makeup Saturday — force rest_day = N,
                    # at kung walang sched times, borrow ng weekday
                    if is_makeup_saturday:
                        rest_day = "N"
                        if not sched_time_in or not sched_time_out:
                            with connection.cursor() as cursor:
                                cursor.execute(
                                    """
                                    SELECT time_in, time_out
                                    FROM employee_schedule_default
                                    WHERE emp_id = %s AND rest_day = 'N'
                                    LIMIT 1
                                    """,
                                    [emp_id],
                                )
                                weekday_sched = cursor.fetchone()
                            if weekday_sched and weekday_sched[0] and weekday_sched[1]:
                                sched_time_in, sched_time_out = weekday_sched[0], weekday_sched[1]

                    # Rest day — laktawan
                    if rest_day == "Y":
                        continue

                    # --- COMPUTE LATE AT UNDERTIME ---
                    late_mins = 0
                    ut_mins = 0

                    if time_in_str and sched_time_in:
                        time_in_dt = datetime.strptime(time_in_str, "%H:%M:%S")
                        sched_in_dt = datetime.strptime(str(sched_time_in), "%H:%M:%S")
                        raw_late = int((time_in_dt - sched_in_dt).total_seconds() / 60)
                        # 5-minute grace period — kung nasa loob, walang late
                        late_mins = raw_late if raw_late > 5 else 0

                    if time_out_str and sched_time_out:
                        time_out_dt = datetime.strptime(time_out_str, "%H:%M:%S")
                        sched_out_dt = datetime.strptime(str(sched_time_out), "%H:%M:%S")
                        raw_ut = int((sched_out_dt - time_out_dt).total_seconds() / 60)
                        # Undertime — charged in 30-minute blocks
                        ut_mins = ((raw_ut + 29) // 30) * 30 if raw_ut > 0 else 0

                    # --- COMPUTE BASIC HOURS ---
                    # Base = maximum hours para sa araw na iyon
                    # Ibabawas ang late at undertime
                    is_holiday = parsed_date in holiday_dates

                    if is_holiday:
                        # Holiday — regular hours, based on employee type
                        if is_compressed_employee:
                            if day_of_week == 1:        # Monday
                                day_max = 600
                            elif 2 <= day_of_week <= 5: # Tuesday-Friday
                                day_max = 570
                            else:                       # Saturday
                                day_max = 480
                        else:
                            day_max = 480               # Regular employee

                    elif is_compressed_employee:
                        if not holidays_in_week:
                            # Walang holiday sa linggo — gamitin ang compressed caps
                            if day_of_week == 1:        # Monday
                                day_max = 600
                            elif 2 <= day_of_week <= 5: # Tuesday-Friday
                                day_max = 570
                            else:                       # Saturday
                                day_max = 480
                        else:
                            # May holiday sa linggo — standard 8 hours lang
                            day_max = 480
                    else:
                        # Regular employee — palaging 8 hours max
                        day_max = 480

                    # I-deduct ang late at undertime sa maximum hours
                    basic_hours = float(max(0, day_max - late_mins - ut_mins))

                    # I-save ang computed timesheet record
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO lp_timesheet
                            (
                                emp_id, tran_date, actual_time_in, actual_time_out,
                                is_rest_day, is_compressed, basic_days, absent_days,
                                late_mins, ut_mins, vl_days, sl_days, basic_hours
                            )
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON DUPLICATE KEY UPDATE
                                actual_time_in  = VALUES(actual_time_in),
                                actual_time_out = VALUES(actual_time_out),
                                is_rest_day     = VALUES(is_rest_day),
                                is_compressed   = VALUES(is_compressed),
                                basic_days      = VALUES(basic_days),
                                absent_days     = VALUES(absent_days),
                                late_mins       = VALUES(late_mins),
                                ut_mins         = VALUES(ut_mins),
                                vl_days         = VALUES(vl_days),
                                sl_days         = VALUES(sl_days),
                                basic_hours     = VALUES(basic_hours)
                            """,
                            [
                                emp_id, parsed_date, time_in_str, time_out_str,
                                rest_day or "N", is_compressed,
                                1.0, 0.0,  # basic_days, absent_days
                                late_mins, ut_mins,
                                0.0, 0.0,  # vl_days, sl_days
                                basic_hours,
                            ],
                        )

                    total_days_worked += 1.0

                except Exception:
                    # I-skip ang record na may error, huwag pabagsakin ang buong upload
                    continue

            # HOLIDAY CREDIT: I-credit ang holidays na nahulog sa pagitan ng work days
            # Halimbawa: Nagtrabaho ng April 1, holiday April 2-4, nagtrabaho ulit April 6
            # I-credit ang April 2, 3, 4
            if all_dates and holiday_dates:
                work_days = sorted(all_dates)

                holidays_between_work_days = []
                for i in range(len(work_days) - 1):
                    check_date = work_days[i] + timedelta(days=1)
                    while check_date < work_days[i + 1]:
                        if check_date in holiday_dates:
                            holidays_between_work_days.append(check_date)
                        check_date += timedelta(days=1)

                for holiday_date in holidays_between_work_days:
                    schedule = get_employee_schedule(emp_id, holiday_date)

                    # I-credit lang kung may schedule at hindi rest day
                    if not (schedule and schedule[0] and schedule[1] and schedule[2] != "Y"):
                        continue

                    sched_time_in, sched_time_out = schedule[0], schedule[1]

                    # For holidays, use standard 480 minutes (8 hours) regardless of compressed schedule
                    basic_hours = 480.0

                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO lp_timesheet
                            (
                                emp_id, tran_date, actual_time_in, actual_time_out,
                                is_rest_day, is_compressed, basic_days, absent_days,
                                late_mins, ut_mins, vl_days, sl_days, basic_hours
                            )
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON DUPLICATE KEY UPDATE
                                actual_time_in  = VALUES(actual_time_in),
                                actual_time_out = VALUES(actual_time_out),
                                is_rest_day     = VALUES(is_rest_day),
                                is_compressed   = VALUES(is_compressed),
                                basic_days      = VALUES(basic_days),
                                absent_days     = VALUES(absent_days),
                                late_mins       = VALUES(late_mins),
                                ut_mins         = VALUES(ut_mins),
                                vl_days         = VALUES(vl_days),
                                sl_days         = VALUES(sl_days),
                                basic_hours     = VALUES(basic_hours)
                            """,
                            [
                                emp_id, holiday_date,
                                sched_time_in.strftime("%H:%M:%S") if sched_time_in else None,
                                sched_time_out.strftime("%H:%M:%S") if sched_time_out else None,
                                "N", is_compressed,
                                1.0, 0.0,           # basic_days, absent_days
                                0, 0,               # Walang late o undertime
                                0.0, 0.0,           # vl_days, sl_days
                                basic_hours,
                            ],
                        )

                    total_days_worked += 1.0

            # Kung walang valid na records sa file
            if valid_entries == 0:
                return Response(
                    {"result": "error", "message": "No valid date entries found in file"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Kunin ang Employee object para sa foreign key
            try:
                employee = Employee.objects.get(emp_id=emp_id)
            except Employee.DoesNotExist:
                return Response(
                    {"result": "error", "message": "Employee not found in Employee table"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # I-save ang summary upload record
            TimesheetRecord.objects.create(
                timesheet_id=timesheet_id,
                emp_id=employee,
                emp_name=emp_name,
                uploaded_by=active_user,
                updated_by=active_user,
            )

            # I-log ang transaction
            GeneralLog.objects.create(
                table_id=emp_id,
                table_name="TimesheetRecord",
                action="CREATE",
                details={
                    "timesheet_id": timesheet_id,
                    "employee_name": emp_name,
                    "employee_id": emp_id,
                    "valid_entries": valid_entries,
                },
                performed_by=active_user,
            )

            return Response(
                {
                    "result": "success",
                    "data": {
                        "timesheet_id": timesheet_id,
                        "message": f"Successfully processed {valid_entries} entries for {emp_name}",
                        "total_days_worked": total_days_worked,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        return Response(
            {"result": "error", "message": f"Error processing file: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def get_timesheet_records(request):
    # Kunin lahat ng uploaded timesheet records na may pagination
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))

        # I-validate ang pagination params
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 25

        offset = (page - 1) * page_size
        total_count = TimesheetRecord.objects.count()

        # Pinaka-recent muna, may pagination
        timesheet_records = (
            TimesheetRecord.objects
            .select_related("emp_id")
            .order_by("-uploaded_at")[offset: offset + page_size]
        )

        serializer = TimesheetRecordSerializer(timesheet_records, many=True)

        return Response(
            {
                "result": "success",
                "data": serializer.data,
                "total": total_count,
                "page": page,
                "page_size": page_size,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"result": "error", "message": f"Error fetching records: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
def delete_timesheet(request, emp_id):
    # Burahin lahat ng timesheet records ng isang employee
    try:
        with transaction.atomic():
            # Hindi pwedeng i-delete kung may quit claim ang employee
            if LastPayRecord.objects.filter(emp_id=emp_id).exists():
                return Response(
                    {
                        "result": "error",
                        "message": f"Cannot delete timesheet: Employee {emp_id} has an existing quit claim",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Kunin ang employee info para sa logs at cleanup
            employee_data = get_employee_data(emp_id)
            emp_name = employee_data[0] if employee_data else "Unknown"
            biometric_id = employee_data[4] if employee_data and len(employee_data) > 4 else None

            with connection.cursor() as cursor:
                # I-delete ang biometric punch records
                if biometric_id:
                    cursor.execute("DELETE FROM lp_inout WHERE biometric_id = %s", [biometric_id])
                    inout_deleted_count = cursor.rowcount
                else:
                    inout_deleted_count = 0

                # I-delete ang detailed timesheet records
                cursor.execute("DELETE FROM lp_timesheet WHERE emp_id = %s", [emp_id])
                deleted_count = cursor.rowcount

                # I-delete ang summary upload records
                cursor.execute("DELETE FROM timesheet_uploads WHERE emp_id = %s", [emp_id])

            active_user = request.data.get("performed_by", "system")

            # I-log ang deletion
            GeneralLog.objects.create(
                table_id=emp_id,
                table_name="TimesheetRecord",
                action="DELETE",
                details={
                    "employee_id": emp_id,
                    "employee_name": emp_name,
                    "deleted_records": deleted_count,
                    "deleted_inout_records": inout_deleted_count,
                },
                performed_by=active_user,
            )

            return Response(
                {
                    "result": "success",
                    "message": (
                        f"Deleted {deleted_count} timesheet records and "
                        f"{inout_deleted_count} biometric in/out records for employee {emp_id}"
                    ),
                },
                status=status.HTTP_200_OK,
            )

    except Exception as e:
        return Response(
            {"result": "error", "message": f"Error deleting timesheet: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )