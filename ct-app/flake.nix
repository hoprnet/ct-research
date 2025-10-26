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

      # Use uv 0.9.x to match Dockerfile (supports Python 3.14)
      # Fetch pre-built binary from GitHub releases
      uvVersion = "0.9.5";
      uvBinary = pkgs.fetchurl {
        url = "https://github.com/astral-sh/uv/releases/download/${uvVersion}/uv-${
          {
            "x86_64-linux" = "x86_64-unknown-linux-gnu";
            "aarch64-linux" = "aarch64-unknown-linux-gnu";
            "x86_64-darwin" = "x86_64-apple-darwin";
            "aarch64-darwin" = "aarch64-apple-darwin";
          }.${system}
        }.tar.gz";
        sha256 = {
          "x86_64-linux" = "2cf10babba653310606f8b49876cfb679928669e7ddaa1fb41fb00ce73e64f66";
          "aarch64-linux" = "9db0c2f6683099f86bfeea47f4134e915f382512278de95b2a0e625957594ff3";
          "x86_64-darwin" = "58b1d4a25aa8ff99147c2550b33dcf730207fe7e0f9a0d5d36a1bbf36b845aca";
          "aarch64-darwin" = "dc098ff224d78ed418e121fd374f655949d2c7031a70f6f6604eaf016a130433";
        }.${system};
      };

      uv-latest = pkgs.stdenv.mkDerivation {
        name = "uv-${uvVersion}";
        src = uvBinary;

        sourceRoot = ".";

        installPhase = ''
          mkdir -p $out/bin
          tar -xzf $src
          install -m755 -D uv-*/uv $out/bin/uv
          install -m755 -D uv-*/uvx $out/bin/uvx
        '';
      };
    in rec {
      devShell = pkgs.mkShell {
        buildInputs = with pkgs; [
          python314    # Python 3.14 to match Dockerfile
          uv-latest    # uv 0.9.5 to match Dockerfile
        ];

        shellHook = ''
          echo "Development environment loaded:"
          echo "  Python: $(python3 --version)"
          echo "  uv: $(uv --version)"
          echo "  uvx: $(uvx --version)"
          echo ""
          uv sync
        '';
      };
    }
  );
}