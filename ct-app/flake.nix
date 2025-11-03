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
    }
  );
}