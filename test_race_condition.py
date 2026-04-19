#!/usr/bin/env python3
"""
Race Condition Test for Payment Webhook Idempotency

This script demonstrates the race condition vulnerability in the webhook
processing system where concurrent identical webhook requests can bypass
idempotency checks and cause duplicate processing.

Usage:
    python test_race_condition.py [--url URL] [--count N] [--payload-file FILE]

Example:
    python test_race_condition.py --url http://localhost:8000/webhooks/stripe --count 5
"""

import asyncio
import json
import argparse
import httpx
from typing import List
import time

# Sample Stripe webhook payload (simplified)
DEFAULT_PAYLOAD = {
    "id": "evt_1OaBCd2eZvKYlo2C5J2p7J8K",
    "type": "payment_intent.succeeded",
    "data": {
        "object": {
            "id": "pi_3OaBCd2eZvKYlo2C1J2p7J8K",
            "amount": 1999,
            "currency": "usd",
            "metadata": {
                "tenant_id": "test_tenant_123",
                "invoice_id": "inv_test_456"
            }
        }
    }
}

async def send_webhook_request(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    request_id: int,
    verbose: bool = False
) -> httpx.Response:
    """Send a single webhook request."""
    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": f"t={int(time.time())},v1=fake_signature_{request_id}",
        "User-Agent": f"TestClient/{request_id}"
    }
    
    if verbose:
        print(f"[Request {request_id}] Sending to {url}")
        print(f"[Request {request_id}] Headers: {headers}")
        print(f"[Request {request_id}] Payload ID: {payload.get('id', 'N/A')}")
    
    try:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        if verbose:
            print(f"[Request {request_id}] Status: {response.status_code}")
            print(f"[Request {request_id}] Headers: {dict(response.headers)}")
            print(f"[Request {request_id}] Response: {response.text[:200]}...")
        else:
            print(f"[Request {request_id}] Status: {response.status_code}, Response: {response.text[:100]}...")
        return response
    except Exception as e:
        print(f"[Request {request_id}] Error: {e}")
        return httpx.Response(status_code=0, text=str(e))

async def test_race_condition(
    url: str,
    payload: dict,
    concurrent_count: int = 2,
    delay_ms: int = 0,
    verbose: bool = False
) -> List[httpx.Response]:
    """
    Send multiple identical webhook requests simultaneously to test for race conditions.
    
    Args:
        url: Webhook endpoint URL
        payload: Webhook payload to send
        concurrent_count: Number of concurrent requests to send
        delay_ms: Delay between launching requests in milliseconds
        verbose: Enable verbose output
        
    Returns:
        List of responses from all requests
    """
    print(f"\n{'='*60}")
    print(f"Testing race condition with {concurrent_count} concurrent requests")
    print(f"Target URL: {url}")
    print(f"Payload ID: {payload.get('id', 'N/A')}")
    print(f"Delay between requests: {delay_ms}ms")
    print(f"Verbose mode: {verbose}")
    print(f"{'='*60}\n")
    
    async with httpx.AsyncClient() as client:
        # Create tasks for concurrent requests
        tasks = []
        for i in range(concurrent_count):
            if delay_ms > 0 and i > 0:
                if verbose:
                    print(f"Waiting {delay_ms}ms before request {i+1}...")
                await asyncio.sleep(delay_ms / 1000.0)
            
            task = send_webhook_request(client, url, payload, i+1, verbose)
            tasks.append(task)
        
        # Send all requests
        if delay_ms == 0:
            print(f"Launching {concurrent_count} concurrent requests simultaneously...")
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            print(f"Launching {concurrent_count} requests with {delay_ms}ms delay between each...")
            responses = []
            for task in tasks:
                response = await task
                responses.append(response)
        
        # Process results
        actual_responses = []
        for i, result in enumerate(responses):
            if isinstance(result, Exception):
                print(f"[Request {i+1}] Exception: {result}")
                actual_responses.append(httpx.Response(status_code=0, text=str(result)))
            else:
                actual_responses.append(result)
        
        return actual_responses

def analyze_results(responses: List[httpx.Response]) -> dict:
    """Analyze the responses to determine if race condition exists."""
    analysis = {
        "total_requests": len(responses),
        "successful_200": 0,
        "successful_2xx": 0,
        "conflict_409": 0,
        "other_4xx": 0,
        "server_5xx": 0,
        "errors": 0,
        "race_condition_detected": False,
        "recommendation": ""
    }
    
    for i, resp in enumerate(responses):
        if resp.status_code == 200:
            analysis["successful_200"] += 1
            analysis["successful_2xx"] += 1
        elif 200 <= resp.status_code < 300:
            analysis["successful_2xx"] += 1
        elif resp.status_code == 409:
            analysis["conflict_409"] += 1
        elif 400 <= resp.status_code < 500:
            analysis["other_4xx"] += 1
        elif 500 <= resp.status_code < 600:
            analysis["server_5xx"] += 1
        elif resp.status_code == 0:
            analysis["errors"] += 1
    
    # Determine if race condition exists
    if analysis["successful_200"] > 1:
        analysis["race_condition_detected"] = True
        analysis["recommendation"] = "CRITICAL: Race condition confirmed! Multiple identical requests processed successfully."
    elif analysis["successful_200"] == 1 and analysis["conflict_409"] >= 1:
        analysis["race_condition_detected"] = False
        analysis["recommendation"] = "GOOD: Idempotency working correctly. Only one request succeeded, others rejected."
    elif analysis["successful_200"] == 1 and analysis["other_4xx"] >= 1:
        analysis["race_condition_detected"] = False
        analysis["recommendation"] = "OK: Only one request succeeded, but error handling could be improved."
    else:
        analysis["recommendation"] = "INCONCLUSIVE: Check server configuration and payload."
    
    return analysis

def print_analysis(analysis: dict):
    """Print the analysis results in a readable format."""
    print(f"\n{'='*60}")
    print("RACE CONDITION ANALYSIS")
    print(f"{'='*60}")
    print(f"Total requests sent: {analysis['total_requests']}")
    print(f"Successful (200): {analysis['successful_200']}")
    print(f"Successful (2xx): {analysis['successful_2xx']}")
    print(f"Conflict (409): {analysis['conflict_409']}")
    print(f"Other client errors (4xx): {analysis['other_4xx']}")
    print(f"Server errors (5xx): {analysis['server_5xx']}")
    print(f"Network/connection errors: {analysis['errors']}")
    print(f"\nRace condition detected: {'YES 🔴' if analysis['race_condition_detected'] else 'NO ✅'}")
    print(f"\nRecommendation: {analysis['recommendation']}")
    
    if analysis['race_condition_detected']:
        print(f"\n⚠️  SECURITY ALERT:")
        print(f"   - Multiple identical webhooks processed successfully")
        print(f"   - Could lead to double payments, duplicate records")
        print(f"   - Fix required: Add transaction isolation or distributed locking")
    print(f"{'='*60}")

def load_payload_from_file(filepath: str) -> dict:
    """Load webhook payload from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading payload from {filepath}: {e}")
        return DEFAULT_PAYLOAD

async def main():
    parser = argparse.ArgumentParser(description="Test race condition in webhook idempotency")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/stripe",
                       help="Webhook endpoint URL (default: http://localhost:8000/webhooks/stripe)")
    parser.add_argument("--count", type=int, default=3,
                       help="Number of concurrent requests (default: 3)")
    parser.add_argument("--delay", type=int, default=0,
                       help="Delay between requests in milliseconds (default: 0)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--payload-file", help="JSON file containing webhook payload")
    parser.add_argument("--tenant-id", help="Override tenant_id in payload metadata")
    
    args = parser.parse_args()
    
    # Load or create payload
    if args.payload_file:
        payload = load_payload_from_file(args.payload_file)
    else:
        payload = DEFAULT_PAYLOAD.copy()
    
    # Override tenant_id if specified
    if args.tenant_id and "data" in payload and "object" in payload["data"]:
        if "metadata" not in payload["data"]["object"]:
            payload["data"]["object"]["metadata"] = {}
        payload["data"]["object"]["metadata"]["tenant_id"] = args.tenant_id
    
    # Run the test
    responses = await test_race_condition(
        args.url, 
        payload, 
        args.count,
        delay_ms=args.delay,
        verbose=args.verbose
    )
    
    # Analyze results
    analysis = analyze_results(responses)
    print_analysis(analysis)
    
    # Save detailed results to file
    results_file = "race_condition_test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "test_configuration": {
                "url": args.url,
                "concurrent_count": args.count,
                "payload_id": payload.get("id", "N/A")
            },
            "responses": [
                {
                    "status_code": r.status_code,
                    "text": r.text[:500] if r.text else "",
                    "headers": dict(r.headers)
                }
                for r in responses
            ],
            "analysis": analysis
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main())