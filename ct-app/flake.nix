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

      # Override uv to use version 0.9.5 (supports Python 3.14) to match Dockerfile
      # This properly builds uv for NixOS with correct library paths
      uv-latest = pkgs.uv.overrideAttrs (oldAttrs: rec {
        version = "0.9.5";

        src = pkgs.fetchFromGitHub {
          owner = "astral-sh";
          repo = "uv";
          rev = version;
          hash = "sha256-Js62zaO44/gXCCwji4LmlyO62zI96CFhnfnYqgI2p+U=";
        };

        # Let Nix re-fetch cargo dependencies for the new version
        cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
          inherit src;
          name = "uv-${version}-vendor";
          hash = "sha256-TadS0YrZV5psCcGiu21w55nQhlzU+gXZPmFCAONLbXE=";
        };
      });

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
          uv-latest    # uv 0.9.5 to match Dockerfile
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