import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

// Replace with your actual backend URL and broker_id
const BACKEND_URL = "http://localhost:8000/api/tokens/refresh/1";

export default function ZerodhaCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const requestToken = searchParams.get("request_token");
    if (!requestToken) {
      alert("No request_token found in callback URL.");
      navigate("/");
      return;
    }

    // Send request_token to backend to refresh Zerodha access token
    fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Add Authorization header if required
        // "Authorization": `Bearer ${your_jwt_token}`,
      },
      body: JSON.stringify({ request_token: requestToken }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "success") {
          alert("Zerodha token refreshed successfully!");
        } else {
          alert("Token refresh failed: " + (data.message || "Unknown error"));
        }
        navigate("/brokers");
      })
      .catch((err) => {
        alert("Error refreshing token: " + err);
        navigate("/brokers");
      });
  }, [searchParams, navigate]);

  return (
    <div style={{ padding: 40 }}>
      <h2>Processing Zerodha Login...</h2>
      <p>Please wait while we refresh your trading token.</p>
    </div>
  );
}
