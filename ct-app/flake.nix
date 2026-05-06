{
  inputs = {
    nixpkgs = {
      url = "github:nixos/nixpkgs/nixos-unstable";
    };
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
  };
  outputs = { nixpkgs, flake-utils, ... }: flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      uvVersion = "0.11.7";
      uvAssets = {
        aarch64-darwin = {
          asset = "uv-aarch64-apple-darwin.tar.gz";
          hash = "sha256-+2SzvIXf9bueaEbukQaxcfjLHvlb/xPNsN7MJgD9vdA=";
        };
        x86_64-darwin = {
          asset = "uv-x86_64-apple-darwin.tar.gz";
          hash = "sha256-0Q16T8AvdLs01VY83vNJcNzsayjClsjcC13EB9EEfQk=";
        };
        aarch64-linux = {
          asset = "uv-aarch64-unknown-linux-gnu.tar.gz";
          hash = "sha256-K3jBQeGuYfiv3FJYmT5C3hoC7buJq9G6JUWmMBLcNMo=";
        };
        x86_64-linux = {
          asset = "uv-x86_64-unknown-linux-gnu.tar.gz";
          hash = "sha256-3ve53WdAGbAefFhEoK0uIsZ0ZTWwB5oAITzxbAUgX7A=";
        };
      };
      uvAsset = uvAssets.${system};
      uvRoot = builtins.replaceStrings [ ".tar.gz" ] [ "" ] uvAsset.asset;

      uv-latest = pkgs.stdenvNoCC.mkDerivation {
        pname = "uv";
        version = uvVersion;

        src = pkgs.fetchzip {
          url = "https://github.com/astral-sh/uv/releases/download/${uvVersion}/${uvAsset.asset}";
          hash = uvAsset.hash;
          stripRoot = false;
        };

        installPhase = ''
          runHook preInstall
          install -Dm755 ${uvRoot}/uv $out/bin/uv
          install -Dm755 ${uvRoot}/uvx $out/bin/uvx
          runHook postInstall
        '';
      };

      buildAndPush = pkgs.writeShellApplication {
          name = "docker-build-and-push";
          runtimeInputs = [
            pkgs.docker
            pkgs.coreutils
          ];
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            if [ -z "''${GOOGLE_ACCESS_TOKEN:-}" ]; then
              echo "[!] ERROR: GOOGLE_ACCESS_TOKEN is not set"
              exit 1
            fi

            if [ -z "''${IMAGE_TARGET:-}" ]; then
              echo "[!] ERROR: IMAGE_TARGET is not set"
              exit 1
            fi

            echo "[+] Logging in to Google Container Registry"
            echo "$GOOGLE_ACCESS_TOKEN" | \
              docker login -u oauth2accesstoken --password-stdin https://europe-west3-docker.pkg.dev

            echo "[+] Building: $IMAGE_TARGET"
            docker build --platform linux/amd64 -t "$IMAGE_TARGET" -f ./Dockerfile .

            echo "[+] Pushing: $IMAGE_TARGET"
            docker push "$IMAGE_TARGET"
            echo "[✓] Done: $IMAGE_TARGET"
          '';
        };

    in rec {
      devShell = pkgs.mkShell {
        buildInputs = with pkgs; [
          python314    # Python 3.14 to match Dockerfile
          uv-latest    # uv 0.11.7 pinned from upstream release binaries
          ruff         # Python linter and formatter
        ];

        shellHook = ''
          echo "Development environment loaded:"
          echo "  Python: $(python3 --version)"
          echo "  uv: $(uv --version)"
          echo "  uvx: $(uvx --version)"
          echo "  ruff: $(ruff --version)"
          echo ""
          uv sync
        '';
      };

      # Expose as flake package + app
      packages.docker-build-and-push = buildAndPush;

      apps.docker-build-and-push = {
        type = "app";
        program = "${buildAndPush}/bin/docker-build-and-push";
      };
    }
  );
}
