#!/usr/bin/env python3
"""
MCP Search Server - A Model Context Protocol server for search functionality
"""

import asyncio
import sys
from typing import Any, Dict, List

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import tts

server = Server("tts-server")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="text_to_audio",
            description="convert text to audio and play",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "text to be played",
                    },
                    "speed": {
                        "type": "number",
                        "description": "play speed, speed should be between 0.5 and 2.0. by default is 1.1",
                    }
                },
                "required": ["text"]
            }
        )
    ]


async def play_audio(audio_data, audio_format):
    import tempfile
    import os
    from pathlib import Path

    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        # Play audio based on platform
        if sys.platform == "darwin":  # macOS
            os.system(f'afplay {temp_path}')
        elif sys.platform == "linux":
            os.system(f'aplay {temp_path}')
        elif sys.platform == "win32":
            os.system(f'start {temp_path}')

        # Cleanup
        Path(temp_path).unlink()
    except Exception as e:
        print(f"Error playing audio: {e}", file=sys.stderr)


async def text_to_speech(args: Dict[str, Any]) -> List[types.TextContent]:
    text = args["text"]
    speed = float(args.get("speed", 1.1))
    tts.play_audio(text, speed)
    return [types.TextContent(
        type="text",
        text="The audio is now playing",
    )]


tools = {
    "text_to_audio": text_to_speech,
}


@server.call_tool()
async def call_tool(name: str, args: Dict[str, Any]) -> List[types.TextContent]:
    return await tools[name](args)


async def main():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    print("Starting MCP Search Server...")
    asyncio.run(main())