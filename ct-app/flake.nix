{
  inputs = {
    nixpkgs = {
      url = "github:nixos/nixpkgs/nixos-unstable";
    };
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
    pre-commit.url = "github:cachix/git-hooks.nix";
    pre-commit.inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs =
    {
      nixpkgs,
      flake-utils,
      pre-commit,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

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

        pre-commit-check = pre-commit.lib.${system}.run {
          src = ../.;
          hooks = {
            check-executables-have-shebangs.enable = true;
            check-shebang-scripts-are-executable.enable = true;
            check-case-conflicts.enable = true;
            check-symlinks.enable = true;
            check-merge-conflicts.enable = true;
            check-added-large-files.enable = true;
            commitizen.enable = true;
            actionlint.enable = true;
            pinact = {
              enable = true;
              name = "pinact";
              description = "Check GitHub Action refs are SHA-pinned and resolvable";
              entry = "${pkgs.writeShellScript "pinact-check" ''
                token="''${GITHUB_TOKEN:-$(${pkgs.gh}/bin/gh auth token 2>/dev/null || true)}"
                if [ -z "$token" ]; then
                  echo "pinact: skipping — no GITHUB_TOKEN and gh not authenticated" >&2
                  exit 0
                fi
                export GITHUB_TOKEN="$token"
                exec ${pkgs.pinact}/bin/pinact run --check
              ''}";
              files = "\\.ya?ml$";
              language = "system";
              pass_filenames = false;
            };
          };
          tools = pkgs;
        };

      in
      rec {
        devShells.ci = pkgs.mkShell {
          packages = [ pkgs.zizmor ];
        };

        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            python314 # Python 3.14 to match Dockerfile
            uv # supports Python 3.14
            ruff # Python linter and formatter
          ];

          shellHook = ''
            echo "Development environment loaded:"
            echo "  Python: $(python3 --version)"
            echo "  uv: $(uv --version)"
            echo "  uvx: $(uvx --version)"
            echo "  ruff: $(ruff --version)"
            echo ""
            uv sync
            ${pre-commit-check.shellHook}
            if [ -z "''${GITHUB_TOKEN:-}" ]; then
              export GITHUB_TOKEN="$(${pkgs.gh}/bin/gh auth token 2>/dev/null || true)"
            fi
          '';
        };

        packages = {
          inherit pre-commit-check;
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
