#!/usr/bin/env python3
"""Interactive Auction House CLI with logout as exit command"""

import click
import sys
from commands.auth import logout, login, whoami, register
from commands.customer import list_auctions, view_auction, place_bid, my_bids
from commands.manager import create_auction, add_item, end_auction
from api_client import APIClient

@click.group()
def cli():
    """Auction House CLI Application"""
    pass

def display_welcome():
    """Display welcome message"""
    print("🏠 Welcome to Auction House CLI!")
    print("=" * 50)
    print("Type 'help' for available commands, 'logout' to exit.\n")

def display_help():
    """Display help for interactive mode"""
    print("""
🏠 Auction House CLI - Interactive Mode

📋 Authentication Commands:
  register        Register a new user
  login           Login to your account
  logout          Logout and exit the CLI
  whoami          Show current user

🏛️ Auction Commands:
  list-auctions   List all active auctions
  view-auction   View auction details (requires auction_id)

🛡️ Customer Commands:
  place-bid      Place a bid (requires item_id amount)
  my-bids         View your bidding history

👑 Manager Commands (requires login):
  create-auction  Create a new auction (requires name)
  add-item        Add item to auction (requires auction_id name opening_price)
  end-auction     End an auction (requires auction_id)

💡 Examples:
  login
  create-auction "Spring Art Collection"
  view-auction 1
  place-bid 123 250.50
  logout

⌨️  Type 'help' to show this message again.
""")

def execute_command(command_input):
    """Parse and execute a command"""
    if not command_input.strip():
        return False

    parts = command_input.strip().split()
    if not parts:
        return False

    cmd_name = parts[0].lower()
    args = parts[1:]

    try:
        # Handle logout specially
        if cmd_name == 'logout':
            if args:
                click.echo("❌ 'logout' command doesn't take arguments")
            else:
                logout()
                return True  # Signal to exit

        # Execute specific commands
        if cmd_name == 'list-auctions':
            list_auctions.main(standalone_mode=False)
        elif cmd_name == 'view-auction':
            view_auction.main(standalone_mode=False, args=args)
        elif cmd_name == 'place-bid':
            place_bid.main(standalone_mode=False, args=args)
        elif cmd_name == 'my-bids':
            my_bids.main(standalone_mode=False)
        elif cmd_name == 'create-auction':
            create_auction.main(standalone_mode=False, args=args)
        elif cmd_name == 'add-item':
            add_item.main(standalone_mode=False, args=args)
        elif cmd_name == 'end-auction':
            end_auction.main(standalone_mode=False, args=args)
        else:
            click.echo(f"❌ Unknown command: {cmd_name}")
            click.echo("   Type 'help' for available commands.")
    except Exception as e:
        click.echo(f"❌ Error executing command: {e}")

    except SystemExit:
        # Command completed normally
        return False

def run_interactive():
    """Run CLI in interactive mode with logout as exit"""
    display_welcome()

    client = APIClient()
    initial_user = client.get_current_user()

    if initial_user:
        click.echo(f"🔑 Logged in as: {initial_user.get('name', 'Unknown')} ({initial_user.get('email', 'Unknown')})")
        click.echo(f"🎭 Role: {initial_user.get('role', 'Unknown')}")
    else:
        click.echo("🔓 Not logged in")

    click.echo()  # Add spacing

    # Interactive loop
    while True:
        try:
            # Show appropriate prompt based on login status
            current_user = client.get_current_user()
            if current_user:
                prompt = f"auction-cli ({current_user['name']})> "
            else:
                prompt = "auction-cli (guest)> "

            command_input = input(prompt)

            if not command_input.strip():
                continue

            # Handle commands
            command_lower = command_input.strip().lower()

            if command_lower in ['help', 'h', '?']:
                display_help()
            elif command_lower == 'logout':
                click.echo("👋 Logging out...")
                logout(args=[])
                click.echo("👋 Goodbye!")
                return
            elif command_lower == 'login':
                login.main(standalone_mode=False, args=[])
                client = APIClient()  # Recreate client to pick up new token
            elif command_lower == 'register':
                register.main(standalone_mode=False, args=[])
            elif command_lower == 'whoami':
                whoami.main(standalone_mode=False, args=[])
            elif command_lower == 'logout':
                click.echo("👋 Logging out...")
                logout.main(standalone_mode=False, args=[])
                click.echo("👋 Goodbye!")
                return
            elif command_lower == 'create-auction':
                create_auction.main(standalone_mode=False, args=[])

        except KeyboardInterrupt:
            click.echo("\n👋 Interrupted. Use 'logout' to exit gracefully.")
            return
        except EOFError:
            click.echo("\n👋 Use 'logout' to exit gracefully.")
            continue  # Stay in app, keep session
        except Exception as e:
            click.echo(f"Error: {e}")

@click.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--interactive', '-i', is_flag=True, help='Run in interactive mode')
def main(interactive):
    """Auction House CLI Application"""
    if interactive or not sys.stdin.isatty():
        # Interactive mode or when piped input is detected
        run_interactive()
    else:
        # Non-interactive mode (default behavior)
        # Register all commands for normal CLI usage
        cli.add_command(register)
        cli.add_command(login)
        cli.add_command(logout)
        cli.add_command(whoami)
        cli.add_command(list_auctions)
        cli.add_command(view_auction)
        cli.add_command(place_bid)
        cli.add_command(my_bids)
        cli.add_command(create_auction)
        cli.add_command(add_item)
        cli.add_command(end_auction)
        
        # Run normal Click CLI
        cli()

if __name__ == '__main__':
    main()
