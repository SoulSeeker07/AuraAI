#!/usr/bin/env python
"""Regression test for voice_enabled configuration in AuraCore"""

from core.aura_core import AuraCore

print("=" * 60)
print("Regression Test: voice_enabled Configuration")
print("=" * 60)

# Test 1: Default behavior (no config)
print("\nTest 1: Default behavior (no config)")
core1 = AuraCore()
assert core1.voice_enabled == False, f'Expected voice_enabled=False, got {core1.voice_enabled}'
print('✓ PASS: Default voice disabled')

# Test 2: Explicit False in config
print('\nTest 2: Explicit False in config')
core2 = AuraCore(config={'voice_enabled': False})
assert core2.voice_enabled == False, f'Expected voice_enabled=False, got {core2.voice_enabled}'
print('✓ PASS: voice_enabled=False works correctly')

# Test 3: Explicit True in config
print('\nTest 3: Explicit True in config')
# Clean up singleton to test fresh instance
if hasattr(AuraCore, '_instance') and AuraCore._instance is not None:
    AuraCore._initialized = False
    AuraCore._instance = None
core3 = AuraCore(config={'voice_enabled': True})
assert core3.voice_enabled == True, f'Expected voice_enabled=True, got {core3.voice_enabled}'
print('✓ PASS: voice_enabled=True works correctly')

print('\n' + "=" * 60)
print('✅ All regression tests passed!')
print('   - Default: voice disabled')
print('   - voice_enabled=False: disabled')
print('   - voice_enabled=True: enabled')
print("=" * 60)
