import spotipy
import random
import re
import os
import sys
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:8080/callback/")
PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID")
SCOPE = "playlist-modify-public playlist-modify-private"

DANCERS_FILE = os.getenv("DANCERS_FILE", "dancers.json")


def load_dancers_data():
    try:
        import dancers_songs
        return dancers_songs.dancers_songs, dancers_songs.dancer_conflicts
    except ImportError:
        print("❌ dancers_songs.py not found.")
        print("   Create it based on dancers_songs.example.py")
        sys.exit(1)


def validate_env():
    """Check that all required environment variables are set."""
    missing = []
    for var in ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_PLAYLIST_ID"]:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   • {var}")
        print("\nCopy .env.example to .env and fill in your values.")
        sys.exit(1)


def get_active_dancers(dancers_songs):
    if len(sys.argv) > 1:
        return sys.argv[1:]

    env_dancers = os.getenv("ACTIVE_DANCERS")
    if env_dancers:
        return [d.strip() for d in env_dancers.split(",") if d.strip()]

    try:
        import dancers_songs as ds
    except ImportError:
        ds = None

    if ds and hasattr(ds, "default_active"):
        return ds.default_active

    return list(dancers_songs.keys())


def check_conflicts(dancer_order, dancer_conflicts):
    conflicts_found = []
    for i in range(1, len(dancer_order)):
        current_dancer = dancer_order[i]
        previous_dancer = dancer_order[i - 1]
        if current_dancer in dancer_conflicts:
            if previous_dancer in dancer_conflicts[current_dancer]:
                conflicts_found.append(
                    f"{current_dancer} doesn't want to dance after {previous_dancer}"
                )
    return conflicts_found


def resolve_dancer_order(working_dancers, dancer_conflicts, max_attempts=100):
    has_conflicts = any(dancer in dancer_conflicts for dancer in working_dancers)

    if not has_conflicts:
        shuffled = working_dancers[:]
        random.shuffle(shuffled)
        return shuffled, []

    best_order = None
    best_conflicts = None
    min_conflict_count = float("inf")

    for attempt in range(max_attempts):
        shuffled = working_dancers[:]
        random.shuffle(shuffled)
        conflicts = check_conflicts(shuffled, dancer_conflicts)

        if not conflicts:
            if attempt > 0:
                print(f"✅ Found valid order after {attempt + 1} attempts")
            return shuffled, []

        if len(conflicts) < min_conflict_count:
            min_conflict_count = len(conflicts)
            best_order = shuffled
            best_conflicts = conflicts

    print(f"⚠️  Could not find a conflict-free order after {max_attempts} attempts")
    print(f"   Using best attempt with {min_conflict_count} conflict(s)")
    return best_order, best_conflicts


def get_all_playlist_uris(sp, playlist_id):
    uris = []
    results = sp.playlist_items(playlist_id, limit=50)
    while results:
        uris += [item["track"]["uri"] for item in results["items"] if item["track"]]
        results = sp.next(results) if results["next"] else None
    return uris


def rebuild_playlist_round_robin(sp, working_dancers, playlist_id, dancers_songs, dancer_conflicts):
    print("🎯 Resolving dancer order with conflict rules...")
    ordered_dancers, conflicts = resolve_dancer_order(working_dancers, dancer_conflicts)

    print("🎲 Dancer order today:")
    print(" → " + " | ".join(ordered_dancers))

    if conflicts:
        print("\n⚠️  WARNING: The following conflicts exist in this order:")
        for conflict in conflicts:
            print(f"   • {conflict}")
        user_input = input("\n❓ Continue with this order anyway? (yes/no): ").strip().lower()
        if user_input not in ["yes", "y"]:
            print("❌ Playlist update cancelled.")
            return
        print()
    else:
        print("✅ All conflict rules respected!")

    # new
    current_uris = get_all_playlist_uris(sp, playlist_id)

    if current_uris:
        sp.playlist_replace_items(playlist_id, [])
        print(f"🧹 Cleared {len(current_uris)} songs from playlist.")

    song_lists = []
    for dancer in ordered_dancers:
        if dancer in dancers_songs:
            song_lists.append(dancers_songs[dancer])
        else:
            print(f"⚠️  No songs defined for dancer '{dancer}'.")

    interleaved_songs = []
    for i in range(max(len(lst) for lst in song_lists)):
        for lst in song_lists:
            if i < len(lst):
                interleaved_songs.append(lst[i])

    valid_uris = [uri for uri in interleaved_songs if uri and uri.startswith("spotify:track:")]

    if len(valid_uris) < len(interleaved_songs):
        print(f"⚠️  Skipped {len(interleaved_songs) - len(valid_uris)} invalid or missing URIs.")

    def chunk_list(lst, chunk_size=100):
        for j in range(0, len(lst), chunk_size):
            yield lst[j: j + chunk_size]

    if valid_uris:
        try:
            for batch_num, chunk in enumerate(chunk_list(valid_uris, 100), 1):
                sp.playlist_add_items(playlist_id, chunk)
                print(f"✅ Added batch {batch_num} ({len(chunk)} songs)")
            print(f"🎉 Successfully added {len(valid_uris)} songs in round-robin order!")
        except Exception as e:
            print(f"\n❌ ERROR while adding songs to Spotify:\n   {str(e)}")
            if "Invalid track uri" in str(e) or "invalid id" in str(e).lower():
                print("\n   Check for malformed track URIs (must be 22-character alphanumeric IDs).")
            raise
    else:
        print("⚠️  No valid songs to add.")


def validate_all_uris(dancers_songs):
    uri_pattern = re.compile(r"^spotify:track:[a-zA-Z0-9]{22}$")
    invalid_uris = []

    for dancer, songs in dancers_songs.items():
        for i, uri in enumerate(songs):
            if not uri:
                invalid_uris.append({"dancer": dancer, "index": i, "uri": uri, "reason": "Empty URI"})
            elif not isinstance(uri, str):
                invalid_uris.append({"dancer": dancer, "index": i, "uri": str(uri), "reason": "URI is not a string"})
            elif not uri.startswith("spotify:track:"):
                invalid_uris.append({"dancer": dancer, "index": i, "uri": uri,
                                     "reason": "Missing 'spotify:track:' prefix"})
            elif not uri_pattern.match(uri):
                track_id = uri.replace("spotify:track:", "")
                reason = (
                    f"Track ID length is {len(track_id)}, should be 22 characters"
                    if len(track_id) != 22
                    else "Invalid characters in track ID"
                )
                invalid_uris.append({"dancer": dancer, "index": i, "uri": uri, "reason": reason})

    return invalid_uris


def print_conflict_rules(dancer_conflicts):
    if not dancer_conflicts:
        print("ℹ️  No conflict rules configured.")
        return
    print("\n📋 Configured Conflict Rules:")
    print("=" * 50)
    for dancer, conflicts_with in dancer_conflicts.items():
        print(f"  • {dancer} doesn't want to dance after: {', '.join(conflicts_with)}")
    print("=" * 50 + "\n")


def main():
    validate_env()

    dancers_songs, dancer_conflicts = load_dancers_data()
    active_dancers = get_active_dancers(dancers_songs)

    # Validate that all active dancers exist in the data
    unknown = [d for d in active_dancers if d not in dancers_songs]
    if unknown:
        print(f"❌ Unknown dancer(s): {', '.join(unknown)}")
        print(f"   Available: {', '.join(dancers_songs.keys())}")
        sys.exit(1)

    print(f"🎶 Active dancers today: {', '.join(active_dancers)}")

    print("\n🔍 Validating Spotify URIs...")
    invalid_uris = validate_all_uris(dancers_songs)

    if invalid_uris:
        print(f"\n❌ Found {len(invalid_uris)} invalid URI(s):\n")
        for issue in invalid_uris:
            print(f"  Dancer: {issue['dancer']}")
            print(f"  Song #{issue['index'] + 1}: {issue['uri']}")
            print(f"  Problem: {issue['reason']}\n")
        print("Fix these URIs in dancers.json before running again.")
        print("Valid format: spotify:track:7ueP5u2qkdZbIPN2YA6LR0")
        sys.exit(1)

    print("✅ All URIs validated successfully!")
    print_conflict_rules(dancer_conflicts)

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
    ))

    rebuild_playlist_round_robin(sp, active_dancers, PLAYLIST_ID, dancers_songs, dancer_conflicts)


if __name__ == "__main__":
    main()
