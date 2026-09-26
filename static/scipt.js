const userId = localStorage.getItem('user_id');

// Products fetch karte waqt user_id query parameter bhejna zaroori hai:
async function fetchProducts() {
    try {
        const res = await fetch(`/products/?user_id=${userId}`);
        if (!res.ok) throw new Error("Products fetch failed");
        const products = await res.json();
        // Render products to table here...
    } catch (err) {
        console.error("Products Error:", err);
    }
}

// Dashboard data fetch karte waqt bhi user_id bhejna zaroori hai:
async function fetchDashboardData() {
    try {
        const res = await fetch(`/dashboard/?user_id=${userId}`);
        if (!res.ok) throw new Error("Dashboard fetch failed");
        const data = await res.json();
        // Render dashboard metrics here...
    } catch (err) {
        console.error("Dashboard Error:", err);
    }
}