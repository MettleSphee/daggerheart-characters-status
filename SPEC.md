# Daggerheart Live Status Page for Characters
I want to create a page for displaying a live status of characters, which will display changes as they're made. Please implement this accordingly.
This will be a python webserver containing 5 different pages:
- A main menu, or the front page, index, whatever, which allows selecting the others;
- The status page, displaying the characters and their statuses;
- The character create/edit/delete page, where multiple users can bring their own character to be displayed in the status page;
- A GM (game master) page, which allows an user to add/remove conditions to players, or directly change values;
- A codex page, for viewing/adding/editing/deleting conditions to be used in the menu.

This project can be inspired from a similar one, found at C:\Users\MettleSphee\Desktop\daggerheart_char_sheet_app. This does not need to be linked to it, but it can use some ideas if absolutely needed.
These pages will be described as follows:

## The character page
This page will allow users to create, edit and delete a character which will be displayed in the status page. The properties of the characters will be as such:
- Name, a text field;
- HP, a number field;
- Marked HP, a series of checkmarks which is based on the number from HP;
- Stress, Marked Stress - same as with HP, Marked HP;
- Armor, Marked Armor - same as with HP, Marked HP;
- Hope, Marked Hope, Scars - same as with HP, Marked HP, with the addition that each Scar will now gray out one of the Marked Hope checkmarks, disabling it entirely, starting from the rightmost one.

Players can also add/remove conditions inflicted on their character, by using a drop-down list of such conditions, from the codex.

## The codex page
This codex page shall allow for users to view, add, edit or delete conditions that are custom. The ability to edit or delete conditons that are default shall not exist, and that shall only apply for new conditions. Newly added conditions shall also not have the same name as others that already exist. Conditions have a name and a description.
The default conditions shall be obtained from the reference page with conditions, as follows:
- Hidden, Restrained and Vulnerable are to be added with their descriptions accordingly;
- Unique conditions (Poisoned, Cursed etc.) are to be added twice, with their descriptions: once normally, and a second time with the addition of "(Temporary)" to the name;
- "Advantage", with the description "Advantage represents an opportunity that you seize to increase your chances of success. When you roll with advantage, you roll a d6 advantage die with your dice pool and add its result to your total.";
- "Disadvantage", with the description "Disadvantage represents an additional difficulty, hardship, or challenge you face when attempting an action. When you roll with disadvantage, you roll a d6 disadvantage die with your dice pool and subtract its result from your total.";
I intend to use badges (inspired from the character sheet, domains) to add flavor to the effects, including colors and an icon, for the Status page. When an icon isn't available, just display the badge without the icon. The colors can be a gradient, just like the badges found earlier.

## The status page 
This page will display the current characters, their values and conditions. Given that the intended screen display is either 16:9 or 9:16, the most amount of player characters displayed should usually be 8. Regardless of actual amount, the display should either show players in rows of 4 (for 16:9 aspect ratio), or rows of 2 (for 9:16 or mobile).
For each player, the following should be displayed:
- Marked HP, with checkmarks being checked accordingly by the user in its character respective page;
- Marked Stress, same as Marked HP;
- Marked Armor, same as Marked HP;
- Marked Hope, with the checkmarks accurate to the Hope and Scars from the earlier page;
- Conditions, a list of the applied conditions, in a single line. These contain the badge which has the name (and icon, if available).
This page is to be updated in real-time on any edit done by the users in any character they're editing.

## The page for the GM
This page is intended to display all available characters, and to be able to edit their values directly, including the inflicted conditions. This should update the changes the players are making, and the players should update the changes made here, in real time. These changes will be reflected in the status page.

## The main menu
This should be the index page (or the front page) of the webapp, and users can select the four pages described earlier. This can be static, as it only needs to link to the other pages.