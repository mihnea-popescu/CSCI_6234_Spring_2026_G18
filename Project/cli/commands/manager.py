import click
from commands.auth import require_auth
from api_client import APIClient

def main(standalone_mode=True):
    """Alternative entry point for standalone mode"""
    if standalone_mode:
        # When called from interactive mode, invoke the original command
        pass  # Will be handled by calling the decorated function directly

@click.command()
@require_auth
def create_auction():
    """Create a new auction"""
    # Verify the user is a manager
    current_user = APIClient().get_current_user()
    if current_user['role'] != 'manager':
        click.echo("❌ You are not authorized to create an auction.")
        return
    client = APIClient()
    result = client.create_auction(name)
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