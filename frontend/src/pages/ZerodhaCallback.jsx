import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import config from "../config/api";

export default function ZerodhaCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const requestToken = searchParams.get("request_token");
    const state = searchParams.get("state");
    const storedBrokerId = localStorage.getItem('zerodha_last_broker_id');
    const parsedBrokerId = state?.includes(':') ? state.split(':')[1] : state;
    const brokerId = parsedBrokerId || storedBrokerId;
    if (!requestToken) {
      alert("No request_token found in callback URL.");
      navigate("/");
      return;
    }
    if (!brokerId) {
      alert("Missing broker id for Zerodha token refresh. Please retry login from Brokers page.");
      navigate("/brokers");
      return;
    }
    const token = localStorage.getItem('access_token');

    // Send request_token to backend to refresh Zerodha access token
    fetch(`${config.API_BASE_URL}/api/tokens/refresh/${brokerId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
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
