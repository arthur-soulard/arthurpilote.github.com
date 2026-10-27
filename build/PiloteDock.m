// PiloteDock.docktileplugin : icone de Pilote dans le Dock quand l'app est
// fermee, a la couleur d'accent (docs/demarrage-et-icone.md).
//
// Le Dock garde en cache l'icone d'une app fermee et ne relit ni l'icone
// posee sur Pilote.app (NSWorkspace) ni celle du paquet (essais du 27/10/2026
// sur macOS 26). Un module de tuile (NSDockTilePlugIn), charge par le Dock
// lui-meme, est la facon prevue par Apple d'y dessiner autre chose.
//
// Il affiche Donnees/icones/dock.png (ecrit par appicon.py) et le relit quand
// Pilote envoie la notification ci-dessous. Sans fichier : l'icone du paquet.
#import <Cocoa/Cocoa.h>
#include <pwd.h>
#include <unistd.h>

static NSString *const kNotification = @"io.github.arthur-soulard.pilote.icone";

@interface PiloteDockTile : NSObject <NSDockTilePlugIn>
@property (strong) NSDockTile *tuile;
@end

@implementation PiloteDockTile

- (void)setDockTile:(NSDockTile *)dockTile {
    NSDistributedNotificationCenter *centre = [NSDistributedNotificationCenter defaultCenter];
    [centre removeObserver:self];
    self.tuile = dockTile;
    if (!dockTile) return;
    [centre addObserver:self selector:@selector(rafraichir:) name:kNotification object:nil
     suspensionBehavior:NSNotificationSuspensionBehaviorDeliverImmediately];
    [self rafraichir:nil];
}

- (void)rafraichir:(NSNotification *)note {
    // Le vrai dossier personnel, meme si le Dock fait tourner le module ailleurs
    struct passwd *pw = getpwuid(getuid());
    NSString *maison = pw ? [NSString stringWithUTF8String:pw->pw_dir] : NSHomeDirectory();
    NSString *chemin = [maison stringByAppendingPathComponent:
                        @"Library/Application Support/Pilote/Donnees/icones/dock.png"];
    NSImage *image = [[NSImage alloc] initWithContentsOfFile:chemin];
    if (image) {
        NSImageView *vue = [NSImageView imageViewWithImage:image];
        vue.imageScaling = NSImageScaleProportionallyUpOrDown;
        self.tuile.contentView = vue;
    } else {
        self.tuile.contentView = nil;
    }
    [self.tuile display];
}

@end
