"""Flask dashboard application for Lavender Ledger."""

import os
from datetime import date
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

from src.dashboard.queries import DashboardQueries
from src.dashboard.terminal import setup_terminal_handlers


def create_app(config: dict = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration dictionary.

    Returns:
        Configured Flask app.
    """
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "templates" / "static"),
    )

    # Load config
    if config is None:
        # Try to load from environment or config file
        db_path = os.environ.get("DATABASE_PATH")
        if not db_path:
            data_dir = os.environ.get("DATA_DIRECTORY", "~/Dropbox/PersonalFinance")
            data_dir = os.path.expanduser(data_dir)
            db_path = os.path.join(data_dir, "finance.db")
        app.config["DATABASE_PATH"] = db_path
    else:
        app.config["DATABASE_PATH"] = config.get("database_path")

    # Initialize queries
    queries = DashboardQueries(app.config["DATABASE_PATH"])

    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Get terminal password from environment
    terminal_password = os.environ.get("TERMINAL_PASSWORD", "lavender")

    # Setup terminal WebSocket handlers
    setup_terminal_handlers(socketio, terminal_password)

    @app.route("/")
    def index():
        """Home page with monthly overview."""
        try:
            available_months = queries.get_available_months()

            # Default to most recent month with data, not current date
            if not request.args.get("year") or not request.args.get("month"):
                if available_months:
                    year, month = available_months[0]  # Most recent month
                else:
                    year = date.today().year
                    month = date.today().month
            else:
                year = request.args.get("year", type=int)
                month = request.args.get("month", type=int)

            summary = queries.get_monthly_summary(year, month)
            top_categories = queries.get_top_categories(year, month, limit=5)
            flagged_count = queries.get_flagged_count(year, month)
            last_updated = queries.get_last_updated()
        except Exception as e:
            # Database might not exist or be empty
            return render_template(
                "index.html",
                error=str(e),
                summary=None,
                top_categories=[],
                available_months=[],
                flagged_count=0,
                last_updated=None,
                current_year=date.today().year,
                current_month=date.today().month,
            )

        return render_template(
            "index.html",
            summary=summary,
            top_categories=top_categories,
            available_months=available_months,
            flagged_count=flagged_count,
            last_updated=last_updated,
            current_year=year,
            current_month=month,
        )

    @app.route("/categories")
    def categories():
        """Category breakdown page."""
        try:
            available_months = queries.get_available_months()
            months_with_expenses = queries.get_available_months_with_expenses()

            # Default to most recent month with expenses for categories page
            if not request.args.get("year") or not request.args.get("month"):
                if months_with_expenses:
                    year, month = months_with_expenses[
                        0
                    ]  # Most recent month with expenses
                elif available_months:
                    year, month = available_months[0]  # Fallback to any month
                else:
                    year = date.today().year
                    month = date.today().month
            else:
                year = request.args.get("year", type=int)
                month = request.args.get("month", type=int)

            breakdown = queries.get_category_breakdown(year, month)
            trend = queries.get_spending_trend(6)
        except Exception as e:
            return render_template(
                "categories.html",
                error=str(e),
                breakdown=[],
                available_months=[],
                trend=[],
                current_year=date.today().year,
                current_month=date.today().month,
            )

        return render_template(
            "categories.html",
            breakdown=breakdown,
            available_months=available_months,
            trend=trend,
            current_year=year,
            current_month=month,
        )

    @app.route("/transactions")
    def transactions():
        """Transaction list page."""
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
        category = request.args.get("category")
        search = request.args.get("search")
        page = request.args.get("page", 1, type=int)
        per_page = 50

        try:
            trans, total = queries.get_transactions(
                year=year,
                month=month,
                category=category,
                search=search,
                limit=per_page,
                offset=(page - 1) * per_page,
            )
            available_months = queries.get_available_months()
            categories = [
                c.category
                for c in queries.get_category_breakdown(
                    year or date.today().year,
                    month or date.today().month,
                )
            ]
        except Exception as e:
            return render_template(
                "transactions.html",
                error=str(e),
                transactions=[],
                available_months=[],
                categories=[],
                total=0,
                page=page,
                pages=0,
                current_year=year,
                current_month=month,
                current_category=category,
                current_search=search,
            )

        pages = (total + per_page - 1) // per_page

        return render_template(
            "transactions.html",
            transactions=trans,
            available_months=available_months,
            categories=categories,
            total=total,
            page=page,
            pages=pages,
            current_year=year,
            current_month=month,
            current_category=category,
            current_search=search,
        )

    @app.route("/trends")
    def trends():
        """Trends and analytics page."""
        try:
            available_months = queries.get_available_months()

            # Default to most recent month with data, not current date
            if not request.args.get("year") or not request.args.get("month"):
                if available_months:
                    year, month = available_months[0]  # Most recent month
                else:
                    year = date.today().year
                    month = date.today().month
            else:
                year = request.args.get("year", type=int)
                month = request.args.get("month", type=int)

            trend = queries.get_spending_trend(12)
            top_merchants = queries.get_top_merchants(year, month, limit=10)
        except Exception as e:
            return render_template(
                "trends.html",
                error=str(e),
                trend=[],
                top_merchants=[],
                available_months=[],
                current_year=date.today().year,
                current_month=date.today().month,
            )

        return render_template(
            "trends.html",
            trend=trend,
            top_merchants=top_merchants,
            available_months=available_months,
            current_year=year,
            current_month=month,
        )

    @app.route("/api/summary/<int:year>/<int:month>")
    def api_summary(year: int, month: int):
        """API endpoint for monthly summary."""
        try:
            summary = queries.get_monthly_summary(year, month)
            return jsonify(
                {
                    "month": summary.month,
                    "total_income": summary.total_income,
                    "total_expenses": summary.total_expenses,
                    "net": summary.net,
                    "transaction_count": summary.transaction_count,
                    "average_daily_spend": summary.average_daily_spend,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/categories/<int:year>/<int:month>")
    def api_categories(year: int, month: int):
        """API endpoint for category breakdown."""
        try:
            breakdown = queries.get_category_breakdown(year, month)
            return jsonify(
                {
                    "categories": [
                        {
                            "name": c.category,
                            "amount": c.amount,
                            "percentage": c.percentage,
                            "color": c.color,
                            "count": c.transaction_count,
                        }
                        for c in breakdown
                    ]
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/health")
    def health():
        """Health check endpoint for Docker."""
        return jsonify({"status": "healthy"})

    @app.route("/terminal")
    def terminal():
        """Terminal page for executing Claude Code commands."""
        return render_template("terminal.html")

    # Store socketio instance on app for access in __main__
    app.socketio = socketio

    return app


# For running directly
if __name__ == "__main__":
    app = create_app()
    app.socketio.run(app, host="0.0.0.0", port=5000, debug=True)
