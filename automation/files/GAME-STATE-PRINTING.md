# Print the Game State

## Start a Monitored Window

1. Open a terminal.
2. Change to the game directory.

   ```bash
   cd "/path/to/DW3 Online"
   ```

3. Start the state-printing launcher.

   ```bash
   ./print-game-state.sh
   ```

4. Log in through the new game window.
5. Move your character.
6. Read the `DW3_STATE` lines in the terminal.

This command opens a new monitored game window.
It does not attach to a window that was already running.
It does not close your existing windows.
Each monitored window uses the normal separate-profile allocation.

The current launcher disables JVM attachment.
An older window without the startup hook cannot provide this internal state output through the script.

## Output

Each line starts with `DW3_STATE ` and contains a JSON object.
The monitor samples approximately every 100 milliseconds.
It prints a new line when the sampled state changes.

Example only:

```text
DW3_STATE {"time":"2026-11-14T00:00:00Z","pid":1234,"profile":"/path/to/profile","phase":"world","screen":"aj","map":"example-map","x":10.75,"y":20.5,"tile_x":10,"tile_y":20,"moving":true,"facing":2}
```

| Field | Meaning |
| --- | --- |
| `time` | The UTC output time. |
| `pid` | The Java process identifier. |
| `profile` | The selected persistent Java home. |
| `phase` | `starting`, `login`, `character_selection`, `loading_map`, `world`, or `other_screen`. |
| `screen` | The internal screen class. |
| `map` | The current map identifier from the client. |
| `x`, `y` | The local player's position in client world coordinates. |
| `tile_x`, `tile_y` | The floor of each position coordinate. |
| `moving` | Whether the position changed since the previous comparable sample. |
| `facing` | The client's direction code, without an assumed compass conversion. |
| `trace` | GPS enabled state, auto-walk state, route type, steps remaining, and remaining route dots. Null outside the world. |

The first world sample has `moving: null` because no previous position exists.
A map or screen change resets the position comparison.
The login screen has no player position, so its position fields are `null`.
A pressed movement key or walking animation alone does not set `moving: true`.

The monitor reads fields on the game render thread.
A separate worker prints the resulting snapshots.
A slow terminal cannot block the render thread through this output path.
The monitor does not write game fields or send movement commands.
It does not print account credentials or network packets.

## Save the Output

Use the following command to display and save the output.

```bash
./print-game-state.sh | tee game-state.log
```

The file contains local position and profile information.
The normal game launch remains unchanged when `DW3_PRINT_STATE` is not set.

## Version and Verification

This monitor supports only the inspected desktop client version 0.1.95.
It verifies the original `app/client.jar` SHA-256 before enabling the observer.
An unsupported client produces a `DW3_STATE_ERROR` message.

The coordinate tests verify movement, idle state, map changes, and animation-only changes.
A separate test verifies that blocked output does not freeze the render thread.
The real client emitted its login state in an isolated graphical test.
Live logged-in movement and GPS route progress have been verified in the monitored window.

For secure login, state files, popup dismissal, and bounded GPS route following,
read [AI-GAME-CONTROL.md](AI-GAME-CONTROL.md).

Run the checks with:

```bash
python3 linux/native/tests/test_state_printer.py
python3 linux/native/tests/test_instances.py
```

The script and source changes are local pending user testing.
