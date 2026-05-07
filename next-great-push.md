# Next Great Push
This docment is to detail the next changes i want to make to Poorup

currently request bailout button doesnt work you need to refresh your page

## Problems with bots and the communist plot mechanic
The bots dont work together and dont contribute to the plot much. at one point 8/10 players were part of the revolution and literally nothing happened because the bots that were contributing were having everything spent immediatly for a million different goals each bot had.
When bots are part of a plot, they need to work together for a common goal set by the leader bot and underlings need to know what to do by being passed on.
When bots are in charge and a player is part of the plot but wasnt the founder or leader, they should be able to see the goal of the bots.

## Liberal Democracy Overhaul
I want a complete overhaul. start from scratch like normal monopoly (basically minarchism).
Make it so each player starts with one random property and random amount of money within a range of 1000-2000.
the rest of the map is owned by 3-6 corporations that you can see the terrotory on th emap. example corporations are:
Blackstone

Prologis

Welltower

Equinix

American Tower

Simon Property Group

Realty Income

Digital Realty

Greystar Real Estate Partners

Brookfield Asset Management

Invitation Homes

Starwood Capital Group

AvalonBay Communities

Crown Castle

Nuveen Real Estate

Morgan Properties

Mid-America Apartment Communities

The Related Companies

Tishman Speyer

Equity Residential

Okay also for airports (this applies to all gamemodes) they are inconsistently named. some go by their abreviation some by only one letter. what i want is for it to say just the abreviation for all airports
Now the whole idea behind the liberal democracy overhaul is this
- You make money through investing in stocks of these companies and crypto (meaning there needs to be a stock market mechanic)
- You can technically buy land but its expensive and all moslty owned by corporations so the main mechanism of earning money is either through getting extremely lucky and affording a set or more commonly through an actual job you are assigned (there needs to be a whole mechanic of raises, bonuses, losing a job, being unemployed for a time, etc. the charater cant impact these its random butdoesnt fluctuate too much. unemployment just mean syour only source of income, go, is a lot less)
- You invest in corporations
- There is a bank (i want the following bank feature in social democracy as well) where you can open a savings account and collect money through interest (disaster can strike). you can also take out loans with interest that you must pay back and it must work like a loan.
lobbying is limited to bailouts, tax bracket mechanics (more later), government giving money to players or printing money, increasing and decreasing wellfair.

now for the idea of tax brackets, the way a player can actually win is through hypermanipulation of tax brackets (they see a 3d pyramid split into segments and where they are and how much each is taxed) where they stand.

now onto jobs. this is another way to win. If a player gets lucky they can use real market manipulation techniques to make the other players lose money or make their jobs pay less. they can request that banks let them borrow other players money not just the bank's so that if they lose the other players also lose. the idea is that to win, you become large neough to gamble with other people's money.

i want the ui to look different i dont want you to just pile new panels i want you to cater it to what really matters in the liberal democracy game mode. that doesnt mean only remove it can also mean to refactor etc.

make sure that you create all the neccessary unit tests and make sure those tests are ran.

one of the ost important things is that the bots are created in a way that they can navigate the liberal democracy and develop an actual strategy. in games with 4+ people they can even have a secret partner who they colude with.

ensure you have tests for these bots and run mock games that actually test for bot behavior rather than just saying that something was a success and that hte behavior leads to victory.


## bot kind refactoring
I like the ability to chose bot difficulty however the personalities are outdated. There should be three personalities and one meant for each game mode. Currently the bots are a mish mash  of personalities that decide what is best in each game mode on a whim however i want to chose economoy mode rather than personality and the bot behavior should accuratly be transfered and emulate the coded behavior that is already there and requested to the liberal democracy changes

## communist plot refactoring
currently members of hte plot are simply poor which is intended but useless. i want the whole system of revolutionary money to work like this:

players have their own money (used to buy, lobby etc)
and there is also a joint bank that a large portion of their money is sent to.

This money is unaffected by tax and is only deducted when revolutionary action is taken. for example when a contribution is made, it draws from the joint account and "laundered". make it clear in no jargo straight forward text in explanation (and progrma this system) thta the more properties owned by revolutionaries the more they can embezzel. 3 properties = 1 support and 2 = 1 support after the first 3 properties. this should be made clear and outlined.

ensure this system of joint account is considered by the bots and made clear to the player

the last clarifying item is that when the player is told bots are going to take a revolutionary action (only to players who are revolutionary) it should not be full of jargon. it should be clear like "increase supply in china" "fortify china" something like that.

Also the way properties are made into theri sections is different than their color sets. for example the light blue properties are two east asia and one oceana. that is confusing. it should just all be oceana. simplify it and reflect that in all panels and plot panel.. all property sets should be in the same region