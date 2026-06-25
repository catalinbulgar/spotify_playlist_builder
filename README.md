# Spotify Playlist Builder

Round-robin playlist builder for club nights. Interleaves songs from active dancers, respects conflict rules (who doesn't want to perform after whom), and pushes the result directly to a Spotify playlist.

## Setup

```bash
pip install spotipy python-dotenv
```

Copy the example files and fill in your values:

```bash
cp .env.example .env
cp dancers_songs.example.py dancers_songs.py
```

## Configuration

### `.env`
| Variable | Description |
|---|---|
| `SPOTIFY_CLIENT_ID` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
| `SPOTIFY_PLAYLIST_ID` | The part after `/playlist/` in the playlist URL |
| `REDIRECT_URI` | Must match what's set in your Spotify app settings |

### `dancers_songs.py`
A regular Python file (gitignored) with three variables:

```python
# Who performs and their songs
dancers_songs = {
    "Natalia": [
        "spotify:track:0DCxlfakEyG4HTzTRGhVVB",  # Erika Isac - Macarena
        "spotify:track:4DFLITLMYKfQjcEnD9TAjv",  # Darkboy - Gangsta Track
    ],
    "Bianca": [
        ...
    ],
}

# Who doesn't want to perform right after whom
dancer_conflicts = {
    "Cristina": ["Natalia", "Raluca"]
}

# Default active dancers when none are specified
default_active = ["Tamara", "Bianca", "Jessica", "Cristina"]
```

Comments are fully supported since it's plain Python.

## Usage

**Use default active dancers** (from `dancers_songs.py` → `default_active`):
```bash
python playlist.py
```

**Specify dancers for tonight via CLI:**
```bash
python playlist.py Tamara Bianca Jessica Cristina
```

**Or set them in `.env`:**
```
ACTIVE_DANCERS=Tamara,Bianca,Jessica
```

Priority: CLI args > `ACTIVE_DANCERS` env var > `default_active` in dancers_songs.py > all dancers.

## New machine setup

```bash
pip install spotipy python-dotenv
cp .env.example .env                        # fill in your credentials
cp dancers_songs.example.py dancers_songs.py  # fill in your songs
python playlist.py                          # browser opens → log in once → .cache created
```

After that first login it runs headlessly on every subsequent run.

## Files

| File | Push to GitHub? |
|---|---|
| `playlist.py` | ✅ Yes |
| `dancers_songs.example.py` | ✅ Yes |
| `.env.example` | ✅ Yes |
| `.gitignore` | ✅ Yes |
| `README.md` | ✅ Yes |
| `.env` | ❌ No — contains secrets |
| `dancers_songs.py` | ❌ No — contains private data |
| `.cache` | ❌ No — contains OAuth token |
