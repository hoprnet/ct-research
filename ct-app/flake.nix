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
      uvVersion = "0.11.25";
      uvAssets = {
        aarch64-darwin = {
          asset = "uv-aarch64-apple-darwin.tar.gz";
          hash = "sha256-YHrKKV2h9msGBt7/JLihVL1z7Lh8PQ0e2obHoyPw9zU=";
        };
        x86_64-darwin = {
          asset = "uv-x86_64-apple-darwin.tar.gz";
          hash = "sha256-8wasGmE8FverjODNqg20v+8n3FInDWfry+VWxoQyD60=";
        };
        aarch64-linux = {
          asset = "uv-aarch64-unknown-linux-gnu.tar.gz";
          hash = "sha256-CdHUtB7rPv7IkmZjgEl6KHFXf5wgkrxWYb4VAOjzjKI=";
        };
        x86_64-linux = {
          asset = "uv-x86_64-unknown-linux-gnu.tar.gz";
          hash = "sha256-NNjGcC9uoe/H8UGs3PaF9f01j6UNP93kS212q9wLkL8=";
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

      dockerBuild = pkgs.writeShellApplication {
          name = "dockerBuild";
          runtimeInputs = [
            pkgs.docker
            pkgs.coreutils
          ];
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            echo "[+] Building: cover-traffic:latest"
            docker build --platform linux/amd64 -t cover-traffic:latest -f ./Dockerfile .
            echo "[✓] Done: cover-traffic:latest"
          '';
        };

    in rec {
      devShells.ci = pkgs.mkShell {
        packages = [ pkgs.zizmor ];
      };

      devShell = pkgs.mkShell {
        buildInputs = with pkgs; [
          python314    # Bootstrap interpreter for uv-managed project Python
          uv-latest    # uv 0.11.25 pinned from upstream release binaries
          ruff         # Python linter and formatter
        ];

        shellHook = ''
          echo "Development environment loaded:"
          echo "  Bootstrap Python: $(python3 --version)"
          echo "  uv: $(uv --version)"
          echo "  uvx: $(uvx --version)"
          echo "  ruff: $(ruff --version)"
          echo ""
          uv sync
          echo "  Project Python: $(uv run python --version)"
        '';
      };

      # Define flake apps
      apps = {
        docker-x86_64-linux = {
          type = "app";
          program = "${dockerBuild}/bin/dockerBuild";
        };
        default = {
          type = "app";
          program = "${dockerBuild}/bin/dockerBuild";
        };
      };
    }
  );
}
