import click
from commands.auth import require_auth
from api_client import APIClient

def main(standalone_mode=True):
    """Alternative entry point for standalone mode"""
    if standalone_mode:
        # When called from interactive mode, invoke the original command
        pass  # Will be handled by calling the decorated function directly

@click.command()
@click.argument('name')
@click.option('--ended-at', default=None, help='End time in ISO format (e.g. 2025-12-31T23:59:59)')
@require_auth
def create_auction(name, ended_at):
    """Create a new auction"""
    # Verify the user is a manager
    current_user = APIClient().get_current_user()
    if current_user['role'] != 'manager':
        click.echo("❌ You are not authorized to create an auction.")
        return
    client = APIClient()
    result = client.create_auction(name=name, ended_at=ended_at)
    if result and 'id' in result:
        click.echo(f"✅ Auction created successfully!")
        click.echo(f"   ID: {result['id']}")
        click.echo(f"   Name: {result['name']}")
        click.echo(f"   Status: {result['status']}")
    else:
        click.echo("❌ Failed to create auction.")

@click.command()
@click.argument('auction_id')
@click.argument('name')
@click.argument('opening_price', type=float)
@require_auth
def add_item(auction_id, name, opening_price):
    """Add item to auction"""
    client = APIClient()
    result = client.add_item(auction_id, name, opening_price)
    if result and 'id' in result:
        click.echo(f"✅ Item added to auction!")
        click.echo(f"   Item ID: {result['id']}")
        click.echo(f"   Name: {result['name']}")
        click.echo(f"   Opening Price: ${result['opening_price']}")
        click.echo(f"   Auction ID: {result['auction_id']}")
    else:
        click.echo("❌ Failed to add item to auction.")

@click.command()
@click.argument('auction_id')
@require_auth
def end_auction(auction_id):
    """End an auction and process results"""
    client = APIClient()
    result = client.end_auction(auction_id)
    if result and 'id' in result:
        click.echo(f"✅ Auction ended successfully!")
        click.echo(f"   ID: {result['id']}")
        click.echo(f"   Name: {result['name']}")
        click.echo(f"   Status: {result['status']}")
        if 'ended_at' in result and result['ended_at']:
            click.echo(f"   Ended At: {result['ended_at']}")
    else:
        click.echo("❌ Failed to end auction.")

@click.command()
@click.argument('auction_id')
@click.option('--name', default=None, help='Name of the auction')
@click.option('--ended-at', default=None, help='End time in ISO format (e.g. 2025-12-31T23:59:59)')
@click.option('--status', default=None, help='Status (e.g. active, ended, cancelled)')
@require_auth
def update_auction(auction_id, name, ended_at, status):
    """Update an auction"""
    if name is None and ended_at is None and status is None:
        click.echo("❌ Provide at least one of: --name, --ended-at, --status")
        return
    client = APIClient()
    result = client.update_auction(auction_id, name=name, ended_at=ended_at, status=status)
    if result and 'id' in result:
        click.echo(f"✅ Auction updated successfully!")
        click.echo(f"   ID: {result['id']}")
        click.echo(f"   Name: {result['name']}")
        click.echo(f"   Status: {result['status']}")
    else:
        click.echo("❌ Failed to update auction.")