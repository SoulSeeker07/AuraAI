#!/usr/bin/env python
"""Fix the voice_listening mode in cli_client.py"""

# Read the file
with open('clients/cli_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the except handlers back (they were removed with the else clause)
except_handlers = '''

            except KeyboardInterrupt:
                print("\\n\\nUse \'quit\' command to exit properly.")
                continue

            except EOFError:
                print("\\n\\n")
                self.running = False
                break

            except Exception as e:
                print(f"\\n✗ Unexpected error: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)'''

# Find the end of the await self.process_command line and add the except handlers
if 'await self.process_command(user_input)\n' in content:
    content = content.replace('await self.process_command(user_input)\n', 'await self.process_command(user_input)' + except_handlers)
    print("✓ Added except handlers back to the file")

# Write the file back
with open('clients/cli_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ File updated")

