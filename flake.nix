{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nci.url = "github:yusdacra/nix-cargo-integration";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pre-commit-hooks = {
      url = "github:cachix/pre-commit-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs:
    inputs.flake-parts.lib.mkFlake {inherit inputs;} {
      imports = [
        inputs.nci.flakeModule
        inputs.pre-commit-hooks.flakeModule
      ];

      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      perSystem = {
        config,
        pkgs,
        ...
      }: let
        projectName = "autokernel";
      in {
        pre-commit.settings.hooks = {
          alejandra.enable = true;
          deadnix.enable = true;
          statix.enable = true;
        };

        nci.projects.${projectName}.path = ./.;
        nci.crates.${projectName} = rec {
          # numtideDevshell = "default";
          runtimeLibs = depsDrvConfig.mkDerivation.buildInputs;
          depsDrvConfig.mkDerivation = {
            nativeBuildInputs = [pkgs.pkg-config];
            buildInputs = with pkgs; [
              luajit
            ];
          };
          drvConfig.mkDerivation = {
            nativeBuildInputs = [pkgs.pkg-config];
            inherit (depsDrvConfig.mkDerivation) buildInputs;
          };
        };

        devShells.default = config.nci.outputs.${projectName}.devShell.overrideAttrs (old: {
          nativeBuildInputs =
            (old.nativeBuildInputs or [])
            ++ [
              pkgs.cargo-release
            ];
          shellHook = ''
            ${old.shellHook or ""}
            ${config.pre-commit.installationScript}
          '';
        });

        packages.default = config.nci.outputs.${projectName}.packages.release;
        formatter = pkgs.alejandra; # `nix fmt`
      };
    };
}
