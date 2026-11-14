"""Frozen launcher keeps the package context required by relative imports."""
from laserforge_native.__main__ import main

raise SystemExit(main())
