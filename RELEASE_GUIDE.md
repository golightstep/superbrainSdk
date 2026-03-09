# Superbrain SDK Release Guide 🚀

This guide explains how to publish the Superbrain SDK to global package managers. Because the SDK relies on a CGO-compiled binary (`libsuperbrain`), follow these steps carefully to ensure cross-platform compatibility.

---

## 1. Go (GitHub)
Go packages are served directly from GitHub.
1.  **Tag the release**:
    ```bash
    git tag -a v0.1.0 -m "Release v0.1.0"
    git push origin v0.1.0
    ```
2.  **Verify**: Users can now run `go get github.com/anispy211/superbrainSdk`.

---

## 2. NPM (Node.js)
Publishing the TypeScript/JavaScript wrapper to the NPM registry.
1.  **Prepare**: Ensure you are in the `node/` directory.
    ```bash
    cd node
    npm install
    # Verify the build
    npx tsc 
    ```
2.  **Publish**:
    ```bash
    # You must be logged in to npm (npm login)
    npm publish --access public
    ```
3.  **Usage**: Users run `npm install @superbrain/sdk`.

---

## 3. PyPI (Python)
Publishing the Python wrapper to the Python Package Index.
1.  **Build**: Ensure you are in the `python/` directory.
    ```bash
    cd python
    python3 -m pip install --upgrade build twine
    python3 -m build
    ```
2.  **Check**:
    ```bash
    python3 -m twine check dist/*
    ```
3.  **Upload**:
    ```bash
    # Requires PyPI credentials
    python3 -m twine upload dist/*
    ```
4.  **Usage**: Users run `pip install superbrain-sdk`.

---

## 🏗️ Handling the Binary SDK
Since we distribute the logic as a compiled shared library (`libsuperbrain.dylib` / `.so`), you have two choices for distribution:

### Option A: Manual Library Download (Current)
Users install the package via their manager, then download the binary from your [GitHub Releases](https://github.com/anispy211/superbrainSdk/releases) and place it in their search path (`LD_LIBRARY_PATH`).

### Option B: Platform-Specific Wheels (Advanced)
In the future, we can use **GitHub Actions** to compile the library for every OS/Architecture combo and bundle it directly into the NPM/PyPI "wheels". This provides a "Zero-Config" experience where `npm install` just works.

---

**Next Steps**: After publishing, update the `README.md` to show the new `pip install` and `npm install` badges!
