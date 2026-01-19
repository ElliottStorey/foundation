#!/bin/bash
set -e

REPO="elliottstorey/foundation"
BINARY="foundation"
DEST="/usr/local/bin"

# 1. Get the download URL for the latest release
URL=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" \
    | grep "browser_download_url" \
    | grep "$BINARY" \
    | head -n 1 \
    | cut -d '"' -f 4)

if [ -z "$URL" ]; then
    echo "Error: Could not find release asset for $REPO"
    exit 1
fi

# 2. Download and Install
echo "Downloading $BINARY..."
curl -L -o "$BINARY" "$URL"
chmod +x "$BINARY"

echo "Installing to $DEST..."
if [ -w "$DEST" ]; then
    mv "$BINARY" "$DEST/$BINARY"
else
    sudo mv "$BINARY" "$DEST/$BINARY"
fi

echo "Success! Run '$BINARY --help' to start."