"""Convert GPS time scalar field values into calendar dates
"""

from datetime import datetime, timedelta, timezone

from .las_metadata import read_las_header


# GPS epoch definition with no leap seconds
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)

# GPS leap second approximation
GPS_UTC_LEAP_SECONDS = 18

# Scaling adjustment for GPS time scalar field
GPS_TIME_ADJUSTMENT = 1_000_000_000

# Sanity check for lidar survey date (assume nothing older than year 2000)
EARLIEST_PLAUSIBLE_SURVEY = datetime(2000, 1, 1, tzinfo=timezone.utc)

# Alternative week format for GPS time in LAS file
SECONDS_PER_GPS_WEEK = 604800


def gps_time_to_utc(
    gps_time,
    adjusted=True
):
    """Converts raw LAS GPS time to UTC date time
    adjusted=True reads it as Adjusted Standard GPS Time (most common)
    adjusted=False reads it as standard GPS time
    """

    seconds = gps_time + (GPS_TIME_ADJUSTMENT if adjusted else 0)

    return GPS_EPOCH + timedelta(seconds=seconds - GPS_UTC_LEAP_SECONDS)


def las_gps_time_is_adjusted(
    header
):
    """Determine whether LAS/LAZ header indicates GpsTime is Adjusted Standard GPS
    Time rather than GPS week time.
    """

    return bool(int(header.get("global_encoding", 0)) & 1)


def _format_day(
    moment
):
    """Format date output"""

    return f"{moment.strftime('%B')} {moment.day}"


def format_date_range(
    first,
    last
):
    """Format date range: "September 10, 2026" for a single day,
    "September 5 to September 7, 2026" within one year, and
    "December 30, 2025 to January 2, 2026" across a new year.
    """

    if first.date() == last.date():

        return f"{_format_day(first)}, {first.year}"

    if first.year == last.year:

        return f"{_format_day(first)} to {_format_day(last)}, {first.year}"

    return (
        f"{_format_day(first)}, {first.year} to "
        f"{_format_day(last)}, {last.year}"
    )


def _is_plausible_survey_date(
    moment
):
    """Determine whether a decoded GpsTime lands in a plausible window.
    """

    return (
        EARLIEST_PLAUSIBLE_SURVEY
        <= moment
        <= datetime.now(timezone.utc) + timedelta(days=1)
    )


def survey_date_range(
    gps_time_range,
    las_files,
    env=None
):
    """Return the calendar dates a dataset was flown as a string
    """

    if not gps_time_range:

        return "not recorded (these files carry no GPS time)"

    claims_adjusted = any(
        las_gps_time_is_adjusted(read_las_header(las_file, env=env))
        for las_file in las_files
    )

    # Quick check if adjusted GPS time looks like week times
    # Could get false positive if survey occurred during September 2011
    looks_like_week_time = (
        0 <= gps_time_range[0]
        and gps_time_range[1] < SECONDS_PER_GPS_WEEK
    )

    if looks_like_week_time and not claims_adjusted:

        return (
            "not recoverable -- these files store GPS week time (seconds "
            "into a GPS week), which records no date"
        )

    for adjusted in (claims_adjusted, not claims_adjusted):

        first, last = (
            gps_time_to_utc(gps_time, adjusted=adjusted)
            for gps_time in gps_time_range
        )

        if not (
            _is_plausible_survey_date(first)
            and _is_plausible_survey_date(last)
        ):

            continue

        dates = format_date_range(first, last)

        if looks_like_week_time:

            dates += (
                f"\n  WARNING: every GPS time here is small enough to be a "
                f"GPS week time, which would carry no date at all. The "
                f"dates above trust the files' global encoding, which says "
                f"otherwise."
            )

        if adjusted != claims_adjusted:

            dates += (
                f"\n  WARNING: the files' global encoding says their GPS "
                f"time is "
                f"{'Adjusted Standard GPS Time' if claims_adjusted else 'GPS week time'}"
                f", but only reading it as "
                f"{'adjusted' if adjusted else 'standard'} GPS time gives a "
                f"sensible date. The dates above assume the header flag is "
                f"wrong."
            )

        return dates

    first, last = (
        gps_time_to_utc(gps_time, adjusted=claims_adjusted)
        for gps_time in gps_time_range
    )

    return (
        f"unreadable (raw GpsTime {gps_time_range[0]:,.1f} to "
        f"{gps_time_range[1]:,.1f})"
        f"\n  WARNING: neither adjusted nor standard GPS time puts these "
        f"files in a plausible survey window -- read as "
        f"{'adjusted' if claims_adjusted else 'standard'} they would be "
        f"{format_date_range(first, last)}. The files most likely store GPS "
        f"week time, which records seconds into a week and so carries no "
        f"date."
    )
