"""Integration tests for the generated Lidarr MCP server.

Run against a live Docker Lidarr instance:
    docker compose -f docker/docker-compose.yml up -d
    bash docker/wait-for-ready.sh
    export LIDARR_URL=http://localhost:8686
    export LIDARR_API_KEY=<key from wait-for-ready.sh>
    nix develop -c pytest tests/test_integration.py -v

All tests are marked ``@pytest.mark.integration`` and auto-skipped when
LIDARR_API_KEY is not set (see conftest.py).
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration


# ── Connection & Auth ────────────────────────────────────────────────────────


async def test_system_status_returns_version(server: ModuleType) -> None:
    """GET /api/v1/system/status returns a dict with 'version'."""
    result = await server.lidarr_list_system_status()
    assert isinstance(result, (dict, list))
    if isinstance(result, dict) and "data" in result:
        # _filter_response wrapper
        assert result["count"] >= 1
    else:
        # Direct dict response
        assert "version" in result


async def test_bad_api_key_returns_structured_error(server: ModuleType) -> None:
    """A request with a bad API key should return a structured error dict."""
    # Save original client state
    original_client = server._client

    # Create a client with a bad key
    bad_client = server.LidarrClient()
    bad_client._client = httpx.AsyncClient(
        base_url=server.LIDARR_URL,
        headers={"X-Api-Key": "definitely-not-a-valid-key"},
        timeout=10.0,
        verify=False,
    )

    try:
        server._client = bad_client
        result = await server.lidarr_get_artist(id=1)
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["source"] == "lidarr_api"
        assert result["status"] in (401, 403)
    finally:
        server._client = original_client
        await bad_client._client.aclose()


# ── High-level tools ────────────────────────────────────────────────────────


async def test_get_overview_keys(server: ModuleType) -> None:
    """lidarr_get_overview returns expected top-level keys."""
    result = await server.lidarr_get_overview()
    assert isinstance(result, dict)
    for key in ("health", "diskSpace", "queueCount", "wantedCount", "artistCount"):
        assert key in result, f"Missing key: {key}"


async def test_search_tools_matching(server: ModuleType) -> None:
    """lidarr_search_tools finds tools matching 'artist'."""
    result = await server.lidarr_search_tools(keyword="artist")
    assert isinstance(result, dict)
    assert result["matches"], "Expected at least one match for 'artist'"
    names = [m["name"] for m in result["matches"]]
    assert any("artist" in n for n in names)


async def test_search_tools_no_match(server: ModuleType) -> None:
    """lidarr_search_tools returns empty list for nonsense keyword."""
    result = await server.lidarr_search_tools(keyword="xyzzy_nonexistent_42")
    assert isinstance(result, dict)
    assert result["matches"] == []


async def test_report_issue_returns_gh_command(server: ModuleType) -> None:
    """lidarr_report_issue returns a gh issue create command string."""
    result = await server.lidarr_report_issue(
        tool_name="lidarr_test_tool",
        error_message="test error",
    )
    assert isinstance(result, str)
    assert "gh issue create" in result


# ── Read operations ──────────────────────────────────────────────────────────


async def test_list_artists_returns_list(server: ModuleType) -> None:
    """lidarr_list_artists returns a filtered response (empty library is fine)."""
    result = await server.lidarr_list_artists()
    assert isinstance(result, dict)
    assert "count" in result
    assert "data" in result
    assert isinstance(result["data"], list)


async def test_list_albums_returns_list(server: ModuleType) -> None:
    """lidarr_list_albums returns a filtered response."""
    result = await server.lidarr_list_albums()
    assert isinstance(result, dict)
    assert "count" in result


async def test_list_root_folders(server: ModuleType) -> None:
    """lidarr_list_root_folders returns a list (may be empty on fresh instance)."""
    result = await server.lidarr_list_root_folders()
    assert isinstance(result, dict)
    assert "count" in result


async def test_list_quality_profiles(server: ModuleType) -> None:
    """lidarr_list_quality_profiles returns at least one profile on a fresh Lidarr."""
    result = await server.lidarr_list_quality_profiles()
    assert isinstance(result, dict)
    assert result["count"] >= 1, "Fresh Lidarr should have at least one quality profile"


# ── List enhancements ────────────────────────────────────────────────────────


async def test_fields_restricts_keys(server: ModuleType) -> None:
    """Passing fields= should restrict keys in each result row (plus 'id')."""
    result = await server.lidarr_list_quality_profiles(fields="name")
    assert isinstance(result, dict)
    if result["count"] > 0:
        row = result["data"][0]
        assert "name" in row
        assert "id" in row  # always included
        # Should not have extra keys beyond id + requested fields
        assert set(row.keys()) <= {"id", "name"}


async def test_filter_filters_rows(server: ModuleType) -> None:
    """Passing filter= should filter rows to only matching ones."""
    # Get all quality profiles first
    all_profiles = await server.lidarr_list_quality_profiles()
    if all_profiles["count"] == 0:
        pytest.skip("No quality profiles to filter")

    first_name = all_profiles["data"][0]["name"]
    filtered = await server.lidarr_list_quality_profiles(
        filter=f"name={first_name}",
    )
    assert isinstance(filtered, dict)
    assert filtered["count"] >= 1
    for row in filtered["data"]:
        assert row["name"] == first_name


# ── CRUD lifecycle ───────────────────────────────────────────────────────────


async def _get_setup_ids(server: ModuleType) -> tuple[int, str]:
    """Get a quality profile ID and root folder path for artist creation.

    Creates a root folder if none exists, and returns the first quality profile.
    """
    qp = await server.lidarr_list_quality_profiles()
    quality_profile_id = qp["data"][0]["id"]

    rf = await server.lidarr_list_root_folders()
    if rf["count"] > 0:
        root_folder = rf["data"][0]["path"]
    else:
        # Create a root folder pointing to the Docker volume mount
        root_folder = "/music"
        result = await server.lidarr_create_root_folder(
            path="/music",
            name="Music",
            defaultQualityProfileId=quality_profile_id,
            defaultMetadataProfileId=1,
            confirm=True,
        )
        assert isinstance(result, dict) and not result.get("error"), (
            f"Failed to create root folder: {result}"
        )

    return quality_profile_id, root_folder


async def test_crud_artist_lifecycle(server: ModuleType) -> None:
    """Full CRUD: lookup → create → get → update → verify → delete → 404."""
    quality_profile_id, root_folder = await _get_setup_ids(server)

    # Step 1: Lookup Metallica to get a valid foreignArtistId
    lookup = await server.lidarr_lookup_artist(term="Metallica")
    assert isinstance(lookup, dict)
    assert lookup["count"] > 0, "Metallica lookup should return results"
    artist_data = lookup["data"][0]
    foreign_id = artist_data["foreignArtistId"]
    assert foreign_id, "Expected a foreignArtistId from lookup"

    # Clean up any leftover artist from a previous failed run
    existing = await server.lidarr_list_artists(filter=f"foreignArtistId={foreign_id}")
    if isinstance(existing, dict) and existing.get("count", 0) > 0:
        for artist in existing["data"]:
            await server.lidarr_delete_artist(
                id=artist["id"], deleteFiles=True, confirm=True,
            )

    # Step 2: Create artist
    created: dict[str, Any] = await server.lidarr_create_artist(
        artistName="Metallica",
        foreignArtistId=foreign_id,
        qualityProfileId=quality_profile_id,
        metadataProfileId=1,
        rootFolderPath=root_folder,
        monitored=False,
        confirm=True,
    )
    assert isinstance(created, dict)
    assert not created.get("error"), f"Create failed: {created}"
    artist_id: int = created["id"]

    try:
        # Step 3: Get artist by ID
        fetched = await server.lidarr_get_artist(id=artist_id)
        assert isinstance(fetched, dict)
        assert fetched["artistName"] == "Metallica"
        assert fetched["id"] == artist_id

        # Step 4: Update artist (toggle monitored)
        # Lidarr's PUT requires the full artist object, so pass all
        # required fields from the fetched object along with the change.
        updated = await server.lidarr_update_artist(
            id=str(artist_id),
            artistName=fetched["artistName"],
            foreignArtistId=fetched["foreignArtistId"],
            qualityProfileId=fetched["qualityProfileId"],
            metadataProfileId=fetched["metadataProfileId"],
            path=fetched.get("path"),
            monitored=True,
            confirm=True,
        )
        assert isinstance(updated, dict)
        assert not updated.get("error"), f"Update failed: {updated}"

        # Step 5: Verify update
        refetched = await server.lidarr_get_artist(id=artist_id)
        assert isinstance(refetched, dict)
        assert refetched["monitored"] is True
    finally:
        # Step 6: Delete artist (cleanup)
        deleted = await server.lidarr_delete_artist(
            id=artist_id,
            deleteFiles=True,
            confirm=True,
        )
        assert isinstance(deleted, dict)
        assert not deleted.get("error"), f"Delete failed: {deleted}"

    # Step 7: Verify 404 after deletion
    gone = await server.lidarr_get_artist(id=artist_id)
    assert isinstance(gone, dict)
    assert gone.get("error") is True
    assert gone["status"] == 404


# ── Merge partial update ──────────────────────────────────────────────────────


async def test_update_artist_merge_partial(server: ModuleType) -> None:
    """Update artist with only one field using merge=True (default).

    merge=True auto-fetches the existing object, merges the caller's changes,
    and PUTs the complete result, so callers don't need to pass all fields.

    Uses Radiohead (not Metallica) to avoid Lidarr race condition on delete
    when running after test_crud_artist_lifecycle.
    """
    quality_profile_id, root_folder = await _get_setup_ids(server)

    # Lookup and create an artist (Radiohead to avoid collision with CRUD test)
    lookup = await server.lidarr_lookup_artist(term="Radiohead")
    assert isinstance(lookup, dict) and lookup["count"] > 0
    artist_data = lookup["data"][0]
    foreign_id = artist_data["foreignArtistId"]

    # Clean up leftover from a previous run
    existing = await server.lidarr_list_artists(filter=f"foreignArtistId={foreign_id}")
    if isinstance(existing, dict) and existing.get("count", 0) > 0:
        for artist in existing["data"]:
            await server.lidarr_delete_artist(
                id=artist["id"], deleteFiles=True, confirm=True,
            )

    created: dict[str, Any] = await server.lidarr_create_artist(
        artistName="Radiohead",
        foreignArtistId=foreign_id,
        qualityProfileId=quality_profile_id,
        metadataProfileId=1,
        rootFolderPath=root_folder,
        monitored=False,
        confirm=True,
    )
    assert isinstance(created, dict) and not created.get("error"), f"Create failed: {created}"
    artist_id: int = created["id"]

    try:
        # Partial update: only pass monitored=True, rely on merge to fill the rest
        updated = await server.lidarr_update_artist(
            id=str(artist_id),
            monitored=True,
            merge=True,
            confirm=True,
        )
        assert isinstance(updated, dict)
        assert not updated.get("error"), f"Merge update failed: {updated}"
        assert updated.get("monitored") is True

        # Verify the update stuck
        refetched = await server.lidarr_get_artist(id=artist_id)
        assert isinstance(refetched, dict)
        assert refetched["monitored"] is True
        # Verify merge didn't lose artist name
        assert refetched["artistName"] == "Radiohead"
    finally:
        await server.lidarr_delete_artist(
            id=artist_id, deleteFiles=True, confirm=True,
        )


# ── Command tools ────────────────────────────────────────────────────────────


async def test_command_missing_album_search(server: ModuleType) -> None:
    """lidarr_command_missing_album_search executes without error."""
    result = await server.lidarr_command_missing_album_search(confirm=True)
    assert isinstance(result, dict)
    assert not result.get("error"), f"Command failed: {result}"
    # Lidarr returns command status with an id
    assert "id" in result


# ── Confirmation gates ───────────────────────────────────────────────────────


async def test_create_artist_confirm_false_returns_preview(
    server: ModuleType,
) -> None:
    """create_artist with confirm=False returns a preview, not a real create."""
    result = await server.lidarr_create_artist(confirm=False)
    assert isinstance(result, dict)
    assert "preview" in result
    assert "confirm" in result
    assert result["preview"] == "POST /api/v1/artist"


async def test_delete_artist_confirm_false_returns_preview(
    server: ModuleType,
) -> None:
    """delete_artist with confirm=False returns a preview, not a real delete."""
    result = await server.lidarr_delete_artist(id=999999, confirm=False)
    assert isinstance(result, dict)
    assert "preview" in result
    assert result["preview"] == "DELETE /api/v1/artist/{id}"


# ── Error handling ───────────────────────────────────────────────────────────


async def test_nonexistent_artist_returns_404(server: ModuleType) -> None:
    """Getting a non-existent artist returns structured 404 error."""
    result = await server.lidarr_get_artist(id=999999)
    assert isinstance(result, dict)
    assert result["error"] is True
    assert result["source"] == "lidarr_api"
    assert result["status"] == 404
    assert result["tool"] == "lidarr_get_artist"


async def test_nonexistent_album_returns_error(server: ModuleType) -> None:
    """Getting a non-existent album returns structured error."""
    result = await server.lidarr_get_album(id=999999)
    assert isinstance(result, dict)
    assert result["error"] is True
    assert result["source"] == "lidarr_api"


# ── Unicode ──────────────────────────────────────────────────────────────────


async def test_lookup_with_en_dash_does_not_crash(server: ModuleType) -> None:
    """Lookup with an en-dash (U+2013) in the term should not crash."""
    # The en-dash should be normalized to a regular hyphen before the API call
    result = await server.lidarr_lookup_artist(term="AC\u2013DC")
    # Should succeed (either results or empty list, but not an error/crash)
    assert isinstance(result, dict)
    assert "count" in result or "error" in result


# ── grab_album ────────────────────────────────────────────────────────────


async def test_grab_album_confirm_false_preview(server: ModuleType) -> None:
    """lidarr_grab_album with confirm=False returns a preview."""
    result = await server.lidarr_grab_album(
        artist="Metallica", album="Master of Puppets", confirm=False,
    )
    assert isinstance(result, dict)
    assert "preview" in result
    assert result["artist"] == "Metallica"
    assert result["album"] == "Master of Puppets"


async def test_grab_album_workflow(server: ModuleType) -> None:
    """Full grab_album workflow: create → grab → verify → cleanup."""
    quality_profile_id, root_folder = await _get_setup_ids(server)

    # Lookup to get foreignArtistId for cleanup
    lookup = await server.lidarr_lookup_artist(term="Metallica")
    assert isinstance(lookup, dict) and lookup["count"] > 0
    foreign_id = lookup["data"][0]["foreignArtistId"]

    # Clean up any leftover from previous runs
    existing = await server.lidarr_list_artists(filter=f"foreignArtistId={foreign_id}")
    if isinstance(existing, dict) and existing.get("count", 0) > 0:
        for artist in existing["data"]:
            await server.lidarr_delete_artist(
                id=artist["id"], deleteFiles=True, confirm=True,
            )

    try:
        # Grab an album (this should create the artist and trigger search)
        result = await server.lidarr_grab_album(
            artist="Metallica",
            album="Master of Puppets",
            qualityProfileId=quality_profile_id,
            rootFolderPath=root_folder,
            confirm=True,
        )
        assert isinstance(result, dict)
        assert result.get("ok") is True, f"grab_album failed: {result}"
        assert "artistId" in result
        assert "albumId" in result
        assert result["status"] == "search_triggered"
    finally:
        # Cleanup: find and delete the artist
        existing = await server.lidarr_list_artists(filter=f"foreignArtistId={foreign_id}")
        if isinstance(existing, dict) and existing.get("count", 0) > 0:
            for artist in existing["data"]:
                await server.lidarr_delete_artist(
                    id=artist["id"], deleteFiles=True, confirm=True,
                )


# ── Command polling ───────────────────────────────────────────────────────


async def test_command_with_wait(server: ModuleType) -> None:
    """Command with wait=True should poll and return a status."""
    result = await server.lidarr_command_missing_album_search(
        confirm=True, wait=True, wait_timeout=15,
    )
    assert isinstance(result, dict)
    assert "commandId" in result
    assert result["status"] in ("completed", "failed", "aborted", "timeout")


# ── Batch album monitoring ──────────────────────────────────────────────────


async def test_update_albums_monitored_preview(server: ModuleType) -> None:
    """lidarr_update_albums_monitored with confirm=False returns preview."""
    result = await server.lidarr_update_albums_monitored(
        albumIds=[1, 2, 3], monitored=True, confirm=False,
    )
    assert isinstance(result, dict)
    assert "preview" in result
    assert result["albumIds"] == [1, 2, 3]
    assert result["monitored"] is True


# ── Metadata profile summary ────────────────────────────────────────────────


async def test_metadata_profile_list_allowed_types(server: ModuleType) -> None:
    """lidarr_list_metadata_profiles should return summarized type names."""
    result = await server.lidarr_list_metadata_profiles()
    assert isinstance(result, dict)
    assert result["count"] >= 1, "Fresh Lidarr should have at least one metadata profile"
    profile = result["data"][0]
    # primaryAlbumTypes should be a list of strings (names), not "[N items]"
    assert "primaryAlbumTypes" in profile
    pat = profile["primaryAlbumTypes"]
    assert isinstance(pat, list)
    if pat:
        assert isinstance(pat[0], str), f"Expected string type names, got {type(pat[0])}"


async def test_normalize_unicode_helper(server: ModuleType) -> None:
    """_normalize_unicode replaces exotic chars with ASCII equivalents."""
    fn = server._normalize_unicode
    assert fn("hello\u2013world") == "hello-world"  # en-dash → hyphen
    assert fn("foo\u00a0bar") == "foo bar"  # NBSP → space
    assert fn("clean") == "clean"  # no-op for ASCII
    assert fn("zero\u200bwidth") == "zerowidth"  # ZWSP removed
