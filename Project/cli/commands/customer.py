import click
from commands.auth import require_auth
from api_client import APIClient

@click.command()
def list_auctions():
    """List all auctions with registration status"""
    client = APIClient()
    auctions = client.get_auctions()
    if not auctions:
        click.echo("No auctions found.")
        return
    
    registered = [a for a in auctions if a.get('is_registered')]
    available = [a for a in auctions if not a.get('is_registered')]
    
    if registered:
        click.echo("🎯 Your Registered Auctions:")
        for auction in registered:
            click.echo(f"   📋 {auction['name']} (ID: {auction['id']}) - ✅ Registered")
    
    if available:
        if registered:
            click.echo("")
        click.echo("🏛️  Available Auctions:")
        for auction in available:
            click.echo(f"   📋 {auction['name']} (ID: {auction['id']})")
    
    if not registered and not available:
        click.echo("No active auctions found.")

@click.command()
@click.argument('auction_id', type=int)
@require_auth
def register_auction(auction_id):
    """Register for an auction"""
    client = APIClient()
    result = client.register_for_auction(auction_id)
    if result and 'id' in result:
        click.echo(f"✅ Successfully registered for auction {auction_id}!")
    elif result and 'detail' in result:
        click.echo(f"❌ {result['detail']}")
    else:
        click.echo("❌ Failed to register for auction.")

@click.command()
@click.argument('auction_id', type=int)
@click.argument('item_id', type=int)
@click.argument('amount', type=float)
@require_auth
def place_bid(auction_id, item_id, amount):
    """Place a bid on an item (requires auction_id, item_id, amount)"""
    client = APIClient()
    result = client.place_bid(auction_id, item_id, amount)
    if result and 'id' in result:
        click.echo(f"✅ Bid placed successfully!")
        click.echo(f"   Bid ID: {result['id']}")
        click.echo(f"   Item ID: {result['item_id']}")
        click.echo(f"   Amount: ${result['amount']}")
    elif result and 'detail' in result:
        click.echo(f"❌ {result['detail']}")
    else:
        click.echo("❌ Failed to place bid.")

@click.command()
@click.argument('auction_id')
def view_auction(auction_id):
    """View auction details"""
    client = APIClient()
    auction = client.get_auction(auction_id)
    if auction and 'id' in auction:
        click.echo(f"🏛️  Auction Details:")
        click.echo(f"   ID: {auction['id']}")
        click.echo(f"   Name: {auction['name']}")
        click.echo(f"   Status: {auction['status']}")
        click.echo(f"   Created: {auction.get('created_at', 'Unknown')}")
        if 'items' in auction and auction['items']:
            click.echo(f"   Items: {len(auction['items'])}")
            for item in auction['items']:
                click.echo(f"     🎯 {item['name']} (ID: {item['id']}) - ${item.get('current_bid', 0)}")
    else:
        click.echo(f"❌ Auction not found with ID: {auction_id}")

@click.command()
@require_auth
def my_bids():
    """View user's bidding history"""
    client = APIClient()
    bids = client.get_user_bids()
    if bids:
        click.echo("💰 Your Bids:")
        for bid in bids:
            click.echo(f"   🎯 Item {bid['item_id']}: ${bid['amount']}")
    else:
        click.echo("No bids found.")
