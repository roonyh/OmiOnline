def findWinner(table,tru,handwinner):    
    tot = 0
    wincard = 0
    i = -1
    first = table[0]
    fc = first[0]
    for c in table:
        i=i+1
        cardscore = 0;
        if c[0] == tru:
            cardscore=10+int(c[-1])
        if c[0] == fc:
            cardscore=int(c[-1])
        if cardscore>tot:
            tot=cardscore
            wincard=i
            
    plr = (handwinner+wincard) % 4
    return plr
