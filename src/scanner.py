"""Replay scanner for parsing .slp files to FrameData."""

from pathlib import Path

from slippi import Game
from slippi.id import CSSCharacter

from src.detectors.base import FrameData
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment


def normalize_connect_code(code: str) -> str:
    """Normalize connect code to uppercase with hash separator.

    Accepts both dash (-) and hash (#) separators, returns hash format.
    Examples: "PDL-637" -> "PDL#637", "pdl#637" -> "PDL#637"
    """
    return code.upper().replace("-", "#")


def find_player_port_by_code(replay_path: Path, code: str) -> int | None:
    """Find the port index of a player by their connect code.

    Args:
        replay_path: Path to the .slp replay file
        code: Connect code (e.g., "PDL-637" or "PDL#637")

    Returns:
        Port index (0-3) if found, None otherwise
    """
    game = Game(replay_path)

    if game.metadata is None or game.metadata.players is None:
        return None

    normalized_code = normalize_connect_code(code)

    for port_idx, player in enumerate(game.metadata.players):
        if player is None:
            continue
        if player.netplay is None:
            continue
        if player.netplay.code is None:
            continue
        if normalize_connect_code(player.netplay.code) == normalized_code:
            return port_idx

    return None


def find_player_port_by_codes(replay_path: Path, codes: list[str]) -> int | None:
    """Find the port index of a player by any of their connect codes.

    Useful when a player may use multiple codes (e.g., main and alt).

    Args:
        replay_path: Path to the .slp replay file
        codes: List of connect codes to check

    Returns:
        Port index (0-3) if any code matches, None otherwise
    """
    for code in codes:
        port = find_player_port_by_code(replay_path, code)
        if port is not None:
            return port
    return None


# Map stage IDs to readable names (lowercase, no spaces)
STAGE_NAMES: dict[int, str] = {
    2: "fountain",
    3: "stadium",
    8: "yoshis",
    28: "dreamland",
    31: "battlefield",
    32: "fd",
}


def get_character_name(char: CSSCharacter) -> str:
    """Get lowercase character name from CSS character enum."""
    return char.name.lower().replace("_", "")


def parse_replay_to_frames(
    replay_path: Path,
    player_port: int,
) -> dict[int, list[FrameData]]:
    """Parse a .slp replay file into FrameData for each opponent.

    For singles matches, returns a single entry.
    For doubles matches, returns one entry per opponent (teammates excluded).

    Args:
        replay_path: Path to the .slp file
        player_port: Port index of the player (0-3)

    Returns:
        Dictionary mapping opponent port to list of FrameData
    """
    game = Game(replay_path)

    if game.start is None:
        raise ValueError(f"Replay has no start data: {replay_path}")

    # Determine stage
    stage_id = game.start.stage.value

    # Get player's team (if teams mode)
    player_info = game.start.players[player_port]
    if player_info is None:
        raise ValueError(f"No player at port {player_port}")

    player_team = player_info.team if game.start.is_teams else None

    # Find opponent ports (different team or all others in singles)
    opponent_ports: list[int] = []
    for port_idx, player in enumerate(game.start.players):
        if player is None:
            continue
        if port_idx == player_port:
            continue
        # In teams mode, opponent is on different team
        if player_team is not None:
            if player.team != player_team:
                opponent_ports.append(port_idx)
        else:
            # Singles mode - everyone else is opponent
            opponent_ports.append(port_idx)

    # Build FrameData for each opponent
    result: dict[int, list[FrameData]] = {}

    for opp_port in opponent_ports:
        frames: list[FrameData] = []

        for frame in game.frames:
            # Skip countdown frames (negative index)
            if frame.index < 0:
                continue

            player_port_data = frame.ports[player_port]
            opp_port_data = frame.ports[opp_port]

            # Skip if either port has no data
            if player_port_data is None or opp_port_data is None:
                continue

            player_post = player_port_data.leader.post
            opp_post = opp_port_data.leader.post

            # Skip if post-frame data not available
            if player_post is None or opp_post is None:
                continue

            frames.append(
                FrameData(
                    frame_number=frame.index,
                    player_x=player_post.position.x,
                    player_y=player_post.position.y,
                    player_action_state=player_post.state,
                    player_stocks=player_post.stocks,
                    opponent_x=opp_post.position.x,
                    opponent_y=opp_post.position.y,
                    opponent_action_state=opp_post.state,
                    opponent_stocks=opp_post.stocks,
                    stage_id=stage_id,
                )
            )

        result[opp_port] = frames

    return result


class ReplayScanner:
    """Scanner for extracting moments from Slippi replays."""

    def get_metadata(self, replay_path: Path) -> dict[str, str]:
        """Extract metadata from a replay file.

        Returns dict with: date, stage, player (character name)
        """
        game = Game(replay_path)

        # Date
        date_str = "unknown"
        if game.metadata is not None and game.metadata.date is not None:
            date_str = game.metadata.date.strftime("%Y-%m-%d")

        # Stage
        stage_name = "unknown"
        player_char = "unknown"
        if game.start is not None:
            stage_id = game.start.stage.value
            stage_name = STAGE_NAMES.get(stage_id, "unknown")

            # Find first human player's character (assume port 0 for now)
            for player in game.start.players:
                if player is not None:
                    player_char = get_character_name(player.character)
                    break

        return {
            "date": date_str,
            "stage": stage_name,
            "player": player_char,
        }

    def get_opponent_ports(self, replay_path: Path, player_port: int) -> list[int]:
        """Get list of opponent port indices.

        In singles, returns all other ports.
        In doubles, returns only ports on opposing team.
        """
        game = Game(replay_path)

        if game.start is None:
            return []

        player_info = game.start.players[player_port]
        if player_info is None:
            return []

        player_team = player_info.team if game.start.is_teams else None

        opponent_ports: list[int] = []
        for port_idx, player in enumerate(game.start.players):
            if player is None:
                continue
            if port_idx == player_port:
                continue
            if player_team is not None:
                if player.team != player_team:
                    opponent_ports.append(port_idx)
            else:
                opponent_ports.append(port_idx)

        return opponent_ports

    def get_opponent_character(
        self, replay_path: Path, opponent_port: int
    ) -> str:
        """Get the character name for an opponent port."""
        game = Game(replay_path)
        if game.start is None:
            return "unknown"
        player = game.start.players[opponent_port]
        if player is None:
            return "unknown"
        return get_character_name(player.character)

    def scan_replay(
        self,
        replay_path: Path,
        player_port: int,
        registry: DetectorRegistry,
    ) -> list[TaggedMoment]:
        """Scan a replay for moments using all registered detectors.

        Parses the replay, runs all detectors, and enriches moments with metadata.

        Args:
            replay_path: Path to the .slp file
            player_port: Port index of the player (0-3)
            registry: DetectorRegistry with detectors to run

        Returns:
            List of detected moments with metadata filled in
        """
        # Get base metadata
        metadata = self.get_metadata(replay_path)

        # Parse replay to frames for each opponent
        frames_by_opponent = parse_replay_to_frames(replay_path, player_port)

        all_moments: list[TaggedMoment] = []

        # Run detectors for each opponent
        for opponent_port, frames in frames_by_opponent.items():
            opponent_char = self.get_opponent_character(replay_path, opponent_port)

            # Run all detectors
            moments = registry.run_all(frames, replay_path)

            # Enrich moments with metadata
            for moment in moments:
                moment.metadata.update(metadata)
                moment.metadata["opponent"] = opponent_char

            all_moments.extend(moments)

        return all_moments
