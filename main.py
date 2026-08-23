print("================================")
print("        STUDY OS")
print("================================")

print()
print("Welcome to your personal study system.")
print()

print("1. View subjects")
print("2. View assignments")
print("3. View tasks")
print("4. Exit")

choice = input("\nChoose an option: ")

if choice == "1":
    print("\nYour subjects:")
    print("No subjects added yet.")

elif choice == "2":
    print("\nYour assignments:")
    print("No assignments added yet.")

elif choice == "3":
    print("\nYour tasks:")
    print("No tasks added yet.")

elif choice == "4":
    print("\nGoodbye!")

else:
    print("\nInvalid choice.")
