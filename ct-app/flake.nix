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
    in rec {
      devShell = pkgs.mkShell {
        buildInputs = with pkgs; [
          python39
          python39Packages.venvShellHook
        ];

        venvDir = "./.venv";
        postVenvCreation = ''
          unset SOURCE_DATE_EPOCH
          pip install -U pip setuptools wheel
          pip install -r requirements.txt
        '' + pkgs.lib.optionalString pkgs.stdenv.isLinux ''
          autoPatchelf ./.venv
        '';
      };
    }
  );
}