import os
import sys
import time
import requests
from datetime import datetime
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich import box

# Configuration
GITHUB_API_URL = "https://api.github.com"
REFRESH_INTERVAL = 30

console = Console()

ASCII_LOGO = r"""
[bold cyan]  ____ _ _   _           _     __     ___                         [/]
[bold cyan] / ___(_) |_| |__  _   _| |__  \ \   / (_) _____      _____ _ __ [/]
[bold cyan]| |  _| | __| '_ \| | | | '_ \  \ \ / /| |/ _ \ \ /\ / / _ \ '__|[/]
[bold cyan]| |_| | | |_| | | | |_| | |_) |  \ V / | |  __/\ V  V /  __/ |   [/]
[bold cyan] \____|_|\__|_| |_|\__,_|_.__/    \_/  |_|\___| \_/\_/ \___|_|   [/]
"""

class GitHubViewer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "GitHub-Profile-Viewer-CLI-App"})
        self.max_views = 10
        self.current_views = 0
        self.rate_limit_remaining = 60
        self.rate_limit_reset = 0
        self.status_message = "Ready to start session."

    def update_rate_limits(self, headers):
        """Update rate limit info from response headers."""
        self.rate_limit_remaining = int(headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))
        self.rate_limit_reset = int(headers.get("X-RateLimit-Reset", 0))

    def extract_username(self, input_str):
        """Extract username from a full GitHub URL or return the string if it's just a username."""
        input_str = input_str.strip().rstrip('/')
        if "github.com/" in input_str:
            return input_str.split("github.com/")[-1].split('/')[0]
        return input_str

    def fetch_user_data(self, username):
        """Fetch user profile data from GitHub API."""
        try:
            response = self.session.get(f"{GITHUB_API_URL}/users/{username}")
            self.update_rate_limits(response.headers)
            self.current_views += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"error": "User not found"}
            elif response.status_code == 403:
                return {"error": "Rate limit exceeded"}
            else:
                return {"error": f"API Error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Connection Error: {str(e)}"}

    def fetch_repos(self, username):
        """Fetch user repositories, sorted by stars."""
        params = {"sort": "stargazers_count", "direction": "desc", "per_page": 5}
        try:
            response = self.session.get(f"{GITHUB_API_URL}/users/{username}/repos", params=params)
            self.update_rate_limits(response.headers)
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []

    def verify_creator(self):
        """Verify the creator account and repository exist on GitHub for integrity."""
        try:
            response = self.session.get(f"{GITHUB_API_URL}/repos/exawill/Github-Viewer", timeout=5)
            if response.status_code == 200:
                return True
            if response.status_code == 403:
                # Return the reset timestamp if rate limited
                return int(response.headers.get("X-RateLimit-Reset", 0))
            return False
        except:
            return False

    def create_layout(self):
        """Initialize the layout for the dashboard."""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="profile", ratio=1),
            Layout(name="repos", ratio=2)
        )
        return layout

    def get_profile_panel(self, user):
        """Create a rich panel for user profile info."""
        if "error" in user:
            return Panel(Text(user["error"], style="bold red"), title="Error", box=box.ROUNDED)

        profile_text = Text()
        profile_text.append(f"Name: ", style="bold cyan")
        profile_text.append(f"{user.get('name') or 'N/A'}\n")
        profile_text.append(f"Bio: ", style="bold cyan")
        profile_text.append(f"{user.get('bio') or 'No bio available'}\n")
        profile_text.append(f"Location: ", style="bold cyan")
        profile_text.append(f"{user.get('location') or 'Not specified'}\n")
        profile_text.append(f"Company: ", style="bold cyan")
        profile_text.append(f"{user.get('company') or 'N/A'}\n")
        profile_text.append(f"Blog: ", style="bold cyan")
        profile_text.append(f"{user.get('blog') or 'N/A'}\n\n")
        
        stats_table = Table(show_header=False, box=None, padding=(0, 2))
        stats_table.add_row("[bold magenta]Followers[/]", str(user.get('followers', 0)))
        stats_table.add_row("[bold magenta]Following[/]", str(user.get('following', 0)))
        stats_table.add_row("[bold magenta]Public Repos[/]", str(user.get('public_repos', 0)))
        
        return Panel(
            Group(profile_text, stats_table),
            title=f"[bold green]@{user['login']}[/]",
            subtitle="Profile Info",
            box=box.DOUBLE
        )

    def get_repos_panel(self, repos):
        """Create a rich panel for repositories list."""
        table = Table(title="Top Repositories (by Stars)", box=box.SIMPLE, expand=True)
        table.add_column("Repository", style="bold blue")
        table.add_column("Language", style="magenta")
        table.add_column("Stars", justify="right", style="yellow")
        table.add_column("Forks", justify="right", style="green")

        if not repos:
            return Panel(Text("No repositories found.", justify="center"), title="Repos", box=box.ROUNDED)

        for repo in repos:
            table.add_row(
                repo['name'],
                repo.get('language') or "Unknown",
                str(repo['stargazers_count']),
                str(repo['forks_count'])
            )

        return Panel(table, box=box.ROUNDED)

    def run(self):
        console.clear()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(description="Verifying system integrity...", total=None)
            verification = self.verify_creator()
            
            # If verification returns an integer, it's a rate limit reset timestamp
            while isinstance(verification, int) and verification > 0:
                wait_time = max(0, verification - int(time.time()))
                if wait_time <= 0:
                    verification = self.verify_creator()
                    continue
                
                for i in range(wait_time, 0, -1):
                    progress.update(task, description=f"[bold yellow]Rate limit hit![/] Retrying integrity check in {i}s...")
                    time.sleep(1)
                verification = self.verify_creator()

            if verification is not True:
                console.print("[bold red]Critical Error:[/] System integrity check failed.")
                console.print("[red]Could not verify creator authenticity. Exiting...[/]")
                return

        console.print(ASCII_LOGO)
        console.print("[bold white]Creator : @exawill[/]\n")
        
        query = Prompt.ask("[bold yellow]Enter Github Username or Link[/]")
        if query.lower() == 'exit':
            return
        
        username = self.extract_username(query)
        
        try:
            limit_input = Prompt.ask(
                "[bold yellow]Set max views for this session : (default is until rate limit hits)[/]", 
                default="1000"
            )
            self.max_views = min(max(int(limit_input), 1), 1000000)
        except ValueError:
            self.max_views = 1000
            
        console.print(f"\n[green]Session started with a limit of {self.max_views} views.[/]")
        
        while self.current_views < self.max_views:
            try:
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(description=f"Fetching data for {username}...", total=None)
                    user_data = self.fetch_user_data(username)
                    repos_data = self.fetch_repos(username) if "error" not in user_data else []

                if "error" in user_data:
                    if user_data['error'] == "Rate limit exceeded":
                        wait_time = max(0, self.rate_limit_reset - int(time.time())) + 1
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            transient=True,
                        ) as progress:
                            task = progress.add_task(description="Rate limit hit...", total=None)
                            for i in range(wait_time, 0, -1):
                                progress.update(task, description=f"[bold yellow]Rate limit hit![/] Retrying {username} in {i}s...")
                                time.sleep(1)
                        continue  # Retry same username
                    
                    console.print(f"[bold red]Error:[/] {user_data['error']}")
                    query = Prompt.ask("\n[bold yellow]Enter Github Username or Link (or 'exit' to quit)[/]")
                    if query.lower() == 'exit':
                        break
                    username = self.extract_username(query)
                    continue

                layout = self.create_layout()
                self._update_layout_content(layout, user_data, repos_data)

                console.clear()
                console.print(layout)
                
                watch = Prompt.ask("\nEnter '[bold green]watch[/]' to start auto-refresh every 15s, or press [bold white]Enter[/] to search again", default="")
                
                if watch.lower() == 'watch':
                    self.status_message = f"Starting auto-watch for {username}..."
                    console.clear()
                    with Live(layout, refresh_per_second=1) as live:
                        while self.current_views < self.max_views:
                            try:
                                # Check rate limit
                                if self.rate_limit_remaining <= 1:
                                    wait_time = max(0, self.rate_limit_reset - int(time.time())) + 1
                                    self.status_message = f"Rate limit hit! Pausing for {wait_time}s..."
                                    for i in range(wait_time, 0, -1):
                                        self._update_layout_content(layout, user_data, repos_data, is_watching=True)
                                        time.sleep(1)
                                    self.rate_limit_remaining = 60
                                
                                time.sleep(REFRESH_INTERVAL)
                                
                                user_data = self.fetch_user_data(username)
                                repos_data = self.fetch_repos(username)
                                self.status_message = f"Message: Successfully refreshed {username} at {datetime.now().strftime('%H:%M:%S')}"
                                self._update_layout_content(layout, user_data, repos_data, is_watching=True)
                                
                            except KeyboardInterrupt:
                                break
                    console.clear()
                    console.print("[yellow]Exited Watch Mode.[/]")

                if self.current_views < self.max_views:
                    query = Prompt.ask("\n[bold yellow]Enter Github Username or Link (or 'exit' to quit)[/]")
                    if query.lower() == 'exit':
                        break
                    username = self.extract_username(query)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Exiting...[/]")
                break
            except Exception as e:
                console.print(f"[bold red]An unexpected error occurred:[/] {str(e)}")
                if not sys.stdin.isatty():
                    break
        
        if self.current_views >= self.max_views:
            console.print(f"\n[bold green]Session limit of {self.max_views} views reached. Goodbye![/]")

    def _update_layout_content(self, layout, user, repos, is_watching=False):
        """Helper to update all sections of the dashboard."""
        status = "Watching" if is_watching else "Viewing"
        quota_color = "green" if self.rate_limit_remaining > 20 else "yellow" if self.rate_limit_remaining > 5 else "red"
        
        header_text = (
            f"[bold cyan]{status}: {user['login']}[/] | "
            f"[dim]Update: {datetime.now().strftime('%H:%M:%S')}[/] | "
            f"Views: [bold white]{self.current_views}/{self.max_views}[/] | "
            f"Quota: [bold {quota_color}]{self.rate_limit_remaining}[/]"
        )
        
        layout["header"].update(Panel(header_text, box=box.SIMPLE))
        layout["profile"].update(self.get_profile_panel(user))
        layout["repos"].update(self.get_repos_panel(repos))
        
        footer_content = Group(
            Text(self.status_message, style="bold green" if "Success" in self.status_message else "yellow"),
            Text("Press Ctrl+C to stop monitoring" if is_watching else "Enter 'watch' to loop every 15 seconds", style="dim")
        )
        layout["footer"].update(Panel(footer_content, box=box.SIMPLE))

if __name__ == "__main__":
    viewer = GitHubViewer()
    viewer.run()
