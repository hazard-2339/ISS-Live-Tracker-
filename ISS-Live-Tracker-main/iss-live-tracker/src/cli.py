import argparse
from datetime import UTC, datetime

from src.orbit import build_satellite, compass_point, fetch_tle, find_passes


def main() -> None:
    parser = argparse.ArgumentParser(description="Upcoming satellite passes")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    satellite = build_satellite(*fetch_tle())
    passes = find_passes(satellite, args.lat, args.lon, datetime.now(UTC), hours=args.hours)
    for p in passes:
        minutes, seconds = divmod(p.duration_seconds, 60)
        print(
            f"{p.start:%a %d %b %H:%M:%S} UTC  "
            f"{compass_point(p.start_azimuth_deg):>3} -> {compass_point(p.end_azimuth_deg):<3}  "
            f"peak {p.max_elevation_deg:4.1f} deg at {p.peak:%H:%M:%S}  "
            f"{minutes}m{seconds:02d}s"
        )


if __name__ == "__main__":
    main()