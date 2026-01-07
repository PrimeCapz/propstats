"""
QR Code Generator for PropStats Mission Control
Generates a QR code to access the app on your phone
"""

import qrcode
import socket

def get_local_ip():
    """Get local IP address"""
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def generate_qr_code(url, filename="propstats_qr.png"):
    """Generate QR code for the given URL"""
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    # Add data
    qr.add_data(url)
    qr.make(fit=True)

    # Create image with neon green fill
    img = qr.make_image(fill_color="#00FFA3", back_color="black")

    # Save
    img.save(filename)
    print(f"✅ QR Code generated: {filename}")
    print(f"🔗 URL: {url}")
    return filename

if __name__ == "__main__":
    print("🏀 PropStats Mission Control - QR Code Generator")
    print("=" * 60)

    # Get local IP
    local_ip = get_local_ip()

    print("\n📱 Choose your option:")
    print("1. Local network access (for phone on same WiFi)")
    print("2. Streamlit Cloud deployment (for remote access)")
    print("3. Custom URL")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == "1":
        port = input("Enter Streamlit port (default 8501): ").strip() or "8501"
        url = f"http://{local_ip}:{port}"
        print(f"\n🌐 Local URL: {url}")
        print("⚠️  Make sure:")
        print("   - Streamlit is running (streamlit run app.py)")
        print("   - Phone is on the same WiFi network")
        print(f"   - Firewall allows port {port}")
        generate_qr_code(url)

    elif choice == "2":
        app_url = input("Enter your Streamlit Cloud URL: ").strip()
        if not app_url:
            print("❌ URL required for Streamlit Cloud deployment")
        else:
            if not app_url.startswith("http"):
                app_url = "https://" + app_url
            generate_qr_code(app_url)
            print("\n📤 To deploy to Streamlit Cloud:")
            print("   1. Go to https://share.streamlit.io")
            print("   2. Connect your GitHub repo")
            print("   3. Deploy from branch: claude/nba-stats-dashboard-xIcAi")
            print("   4. Main file: app.py")

    elif choice == "3":
        custom_url = input("Enter custom URL: ").strip()
        if custom_url:
            generate_qr_code(custom_url)
        else:
            print("❌ URL required")

    else:
        print("❌ Invalid choice")

    print("\n✅ Done! Scan the QR code with your phone camera.")
